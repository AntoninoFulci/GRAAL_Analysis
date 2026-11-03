"""Contracts for the Gaussian candle and raw-vector quality diagnostics."""
from dataclasses import replace

import numpy as np
import pytest

from observable_extraction import beam_asymmetry, workflow
from observable_extraction.io.reconstructed_events import read_reconstructed
from observable_extraction.tests.test_reconstructed_events import _write_reconstructed
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events
from observable_extraction.io import reconstructed_events


def test_reader_retains_raw_quality_vectors_and_optional_target(tmp_path):
    path = tmp_path / 'input.root'
    _write_reconstructed(path)
    events = read_reconstructed(path, 'reco')
    np.testing.assert_allclose(events.beam[0], [0, 0, 1.25, 1.25])
    np.testing.assert_allclose(events.missing[0], [0, 0, 0, .94])
    assert events.target is None  # Legacy fixture has no target: never invent it.
    selected = events.take(np.array([True, False]))
    assert selected.beam.shape == (1, 4)
    assert selected.target is None


def test_gaussian_cli_selects_50_percent_model_without_balance_seed():
    args = beam_asymmetry.build_parser().parse_args(['--candle-gaussian'])
    assert args.candle_gaussian
    workflow.validate_candle_options(args)


def test_gaussian_candle_disallows_background_reuse_before_io():
    args = beam_asymmetry.build_parser().parse_args(['--candle-gaussian', '--sideband', 'x.root'])
    with pytest.raises(ValueError, match='sideband'):
        workflow.validate_candle_options(args)


def test_standalone_script_resolves_calibration_package(tmp_path):
    import subprocess
    import sys
    result = subprocess.run([sys.executable, beam_asymmetry.__file__, '--help'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '--candle-gaussian' in result.stdout


def test_gaussian_split_keeps_every_finite_event_without_balancing():
    from types import SimpleNamespace
    events = _synthetic_events()
    n = len(events)
    eta = events.eta_mass_gev.copy()
    eta[-1] = np.nan
    events = replace(events, eta_mass_gev=eta)
    mask = np.arange(n) < n // 3
    model = SimpleNamespace(mask=lambda *_: mask)
    split = reconstructed_events.split_gaussian_candle(events, model)
    assert len(split.core) == n // 3
    assert len(split.tails) == n - n // 3 - 1
    assert split.excluded_nonfinite_count == 1
    assert split.gaussian_model is model


def test_raw_vector_resampling_preserves_quality_fields():
    from observable_extraction.core.systematics import _events_at_indices
    events = _synthetic_events()
    vectors = np.arange(len(events) * 4).reshape(-1, 4)
    events = replace(events, beam=vectors, target=vectors + 1, missing=vectors + 2)
    resampled = _events_at_indices(events, np.array([2, 2, 0]))
    np.testing.assert_equal(resampled.target, (vectors + 1)[[2, 2, 0]])


@pytest.fixture(scope='module')
def gaussian_model():
    from observable_extraction.core.candle import fit_gaussian_candle
    from graal_common.physics.channels import M_ETA, M_PI0
    masses = np.random.default_rng(423).multivariate_normal(
        [M_ETA, M_PI0], [[.012**2, .3*.012*.008], [.3*.012*.008, .008**2]], 6000)
    background = np.random.default_rng(424).uniform([M_ETA-.05, M_PI0-.05], [M_ETA+.05, M_PI0+.05], (1000, 2))
    return fit_gaussian_candle(*np.vstack((masses, background)).T)


def test_gaussian_provenance_roundtrip_and_profile_specific_widths(gaussian_model):
    from pathlib import Path
    from observable_extraction.io.root_input import _parse_candle_contract, _provenance_values
    from observable_extraction.io.candle_metadata import gaussian_candle_provenance
    events = _synthetic_events()
    rng = np.random.default_rng(221)
    masses = rng.multivariate_normal([gaussian_model.eta_center_gev, gaussian_model.pi0_center_gev],
                                    gaussian_model.covariance_gev2, len(events))
    events = replace(events, eta_mass_gev=masses[:, 0], pi0_mass_gev=masses[:, 1])
    from observable_extraction.core.candle import fit_gaussian_candle
    gaussian_model = fit_gaussian_candle(*masses.T)
    split = reconstructed_events.split_gaussian_candle(events, gaussian_model)
    text = '\n'.join(gaussian_candle_provenance(split, len(events), .05))
    contract = _parse_candle_contract(_provenance_values(text), Path('synthetic.root'))
    assert contract.geometry == 'gaussian_ellipse'
    assert contract.balance_method == 'none'
    assert contract.gaussian_model.to_dict() == gaussian_model.to_dict()
    assert contract.full_core_event_count + contract.tail_event_count == len(events)
    with pytest.raises(RuntimeError, match='candle provenance'):
        _parse_candle_contract(_provenance_values(text.replace('candle_boundary=inclusive',
                                                              'candle_boundary=exclusive')), Path('bad.root'))


def test_gaussian_workflow_keeps_nominal_and_writes_controls(tmp_path, monkeypatch, gaussian_model):
    from observable_extraction.core.models import FluxExposure
    from observable_extraction.io.root_input import read_output_contract, read_output_points
    events = _synthetic_events()
    masses = np.random.default_rng(74).multivariate_normal(
        [gaussian_model.eta_center_gev, gaussian_model.pi0_center_gev], gaussian_model.covariance_gev2,
        len(events))
    beam = np.tile([0., 0., 1.15, 1.15], (len(events), 1))
    target = np.tile([0., 0., 0., .938272], (len(events), 1))
    events = replace(events, eta_mass_gev=masses[:, 0], pi0_mass_gev=masses[:, 1],
                     beam=beam, target=target, missing=beam+target-events.eta-events.pi0)
    monkeypatch.setattr(workflow, '_validate_energy_inputs', lambda _: None)
    monkeypatch.setattr(workflow, 'read_reconstructed', lambda *_: events)
    monkeypatch.setattr(workflow, 'load_exposures', lambda *a, **kw: {
        (811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)})
    args = ['--raw-bdt', str(tmp_path/'bdt.root'), '--raw', str(tmp_path/'absent.root'),
            '--output-dir', str(tmp_path), '--estimator', 'ratio', '--candle-gaussian']
    assert beam_asymmetry.main(args) == 0
    contract = read_output_contract(tmp_path/'beam_asymmetry.root').candle
    assert contract.geometry == 'gaussian_ellipse'
    assert contract.baseline_event_count == len(events)
    points = read_output_points(tmp_path/'beam_asymmetry.root')
    assert {item.sample for item in points} == {'raw_bdt', 'raw_bdt_core', 'raw_bdt_tails'}
    assert (tmp_path/'candle_quality'/'quality_audit.json').is_file()
    assert (tmp_path/'candle_comparison.json').is_file()
    assert (tmp_path/'candle_mass_plane.pdf').read_bytes().startswith(b'%PDF-')
