"""Reconstruction diagnostics consume explicit products without extraction artifacts."""
from __future__ import annotations

import hashlib
import json
from itertools import product

import pytest
import ROOT

from scripts import plot_campaign
from tests.test_plot_campaign import _certify_dalitz_fixture, _write_reconstruction


def _inputs(tmp_path, *, certified=True):
    paths = [tmp_path / 'external' / f'{tag}.root' for tag in ('chi2', 'bdt')]
    for path, tag in zip(paths, ('chi2', 'bdt')):
        _write_reconstruction(path, f'reco_eta_pi0_{tag}', fit=False, certified=certified)
        if certified:
            _certify_dalitz_fixture(path)
    return paths


def _command(paths, output, profile='uv'):
    return ['--reconstruction-only', '--profile', profile, '--chi2', str(paths[0]),
            '--bdt', str(paths[1]), '--output-dir', str(output)]


def _snapshot(directory):
    return {str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}


@pytest.mark.parametrize('mass,quality,dalitz', list(product((False, True), repeat=3)))
def test_reconstruction_plot_switches_control_real_pdfs_and_root(tmp_path, mass, quality, dalitz):
    paths = _inputs(tmp_path)
    before = _snapshot(paths[0].parent)
    output = tmp_path / 'diagnostics'
    switches = [f'--{"" if enabled else "no-"}{name}' for name, enabled in
                [('mass', mass), ('quality-controls', quality), ('dalitz', dalitz)]]
    assert plot_campaign.main(_command(paths, output) + switches) == 0
    names = {path.name for path in output.glob('*.pdf')}
    assert ('massa_eta.pdf' in names) is mass
    assert ('masse_2d_confronto.pdf' in names) is mass
    assert ('missing_mass.pdf' in names) is quality
    assert ('dalitz_confronto.pdf' in names) is dalitz
    if not mass:
        assert not any(name.startswith(('massa_', 'masse_')) for name in names)
    source = ROOT.TFile.Open(str(output / 'istogrammi.root'))
    try:
        metadata = json.loads(source.Get('dalitz_metadata').GetTitle())
        histograms = json.loads(source.Get('histogram_dictionary').GetTitle())
        assert metadata['selection_comparison'] == 'matched_except_bdt_gate'
        assert metadata['samples']['chi2']['entries'] == 1
        assert ('massa_eta_chi2' in histograms) is mass
        assert ('missing_mass_chi2' in histograms) is quality
        assert ('dalitz_chi2_misurato' in histograms) is dalitz
        assert bool(source.Get('quality_metadata')) is quality
    finally:
        source.Close()
    assert _snapshot(paths[0].parent) == before
    assert {path.name for path in tmp_path.iterdir()} == {'external', 'diagnostics'}


@pytest.mark.parametrize('profile', ['uv', 'vis'])
def test_reconstruction_plot_defaults_need_no_extraction(tmp_path, profile):
    paths = _inputs(tmp_path)
    output = tmp_path / 'diagnostics'
    assert plot_campaign.main(_command(paths, output, profile)) == 0
    assert (output / 'massa_eta.pdf').read_bytes().startswith(b'%PDF-')
    assert (output / 'missing_mass.pdf').read_bytes().startswith(b'%PDF-')
    assert not list(output.glob('dalitz*.pdf'))


def test_reconstruction_plot_rejects_uncertified_inputs_without_replacing_output(tmp_path):
    paths = _inputs(tmp_path, certified=False)
    output = tmp_path / 'diagnostics'
    output.mkdir()
    (output / 'existing.pdf').write_bytes(b'keep')
    with pytest.raises(ValueError, match='provenance'):
        plot_campaign.main(_command(paths, output))
    assert _snapshot(output) == {'existing.pdf': hashlib.sha256(b'keep').hexdigest()}


def test_reconstruction_plot_cannot_replace_external_input_directory(tmp_path):
    paths = _inputs(tmp_path)
    before = _snapshot(paths[0].parent)
    with pytest.raises(ValueError, match='input|reconstruction'):
        plot_campaign.main(_command(paths, paths[0].parent))
    assert _snapshot(paths[0].parent) == before


@pytest.mark.parametrize('missing', ['--profile', '--chi2', '--bdt', '--output-dir'])
def test_reconstruction_plot_requires_explicit_products_and_destination(tmp_path, missing):
    args = _command([tmp_path / 'chi2.root', tmp_path / 'bdt.root'], tmp_path / 'out')
    index = args.index(missing)
    del args[index:index + 2]
    with pytest.raises(SystemExit) as exc:
        plot_campaign.main(args)
    assert exc.value.code == 2
