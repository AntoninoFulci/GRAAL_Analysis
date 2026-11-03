"""Physical controls must retain the selected population and raw conventions."""
from dataclasses import replace
import json

import numpy as np
import pytest

from observable_extraction.io.reconstructed_events import EventArrays
from observable_extraction.plotting import candle_quality as quality


def _events():
    n = 3
    return EventArrays(
        run_number=np.arange(n), xstrip=np.zeros(n), polarization=np.ones(n),
        beam_energy_gev=np.array([1.2, 2., 2.]),
        eta=np.array([[.2, 0., 0., .55], [0., 0., 0., 1.], [1., 0., 0., 1.]]),
        pi0=np.array([[.1, 0., 0., .14], [0., 0., 0., 1.], [0., 0., 0., .1]]),
        proton=np.array([[-.3, 0., .4, .99], [0., 0., 0., 0.], [0., 0., 1., 2.]]),
        missing_mass_gev=np.full(n, 99.), eta_mass_gev=np.array([.54, .55, np.nan]),
        pi0_mass_gev=np.array([.13, .14, .15]), bdt_score=np.ones(n),
        n_photons_input=np.full(n, 4),
        beam=np.array([[0., 0., 1.2, 1.2], [0., 0., 2., 2.], [0., 0., 2., 2.]]),
        target=np.array([[0., 0., 0., .938], [0., 0., 0., 1.], [0., 0., 0., 1.]]),
        missing=np.array([[-.3, 0., 1.2, 1.448], [0., 0., 0., 0.], [0., 0., 2., 3.]]),
    )


def test_actual_quality_quantities_and_undefined_directions():
    values = quality.candle_quality_observables(_events())
    assert values['proton_theta_deg'][0] == pytest.approx(36.86989765)
    assert values['theta_missing_proton_deg'][0] == pytest.approx(-22.83365418)
    assert values['coplanarity_deg'][0] == pytest.approx(0.)
    assert values['missing_mass_gev'][0] == pytest.approx(np.sqrt(1.448**2 - 1.53))
    assert values['missing_mass_gev'][1] == pytest.approx(-np.sqrt(3.))
    assert np.isnan(values['theta_missing_proton_deg'][1])
    assert np.isnan(values['coplanarity_deg'][1:]).all()
    assert values['proton_theta_deg'][2] == 0.
    assert values['theta_missing_proton_deg'][2] == 0.
    assert all(len(value) == 3 for value in values.values())


@pytest.mark.parametrize('proton_phi,pair_phi,expected', [
    (179., -1., 0.), (-179., 1., 0.), (-179., -1., 2.), (179., 1., -2.),
])
def test_signed_coplanarity_wrap(proton_phi, pair_phi, expected):
    events = _events()
    def vector(phi):
        angle = np.radians(phi)
        return [np.cos(angle), np.sin(angle), 1., 2.]
    events.proton[0] = vector(proton_phi)
    events.eta[0] = vector(pair_phi)
    events.pi0[0] = vector(pair_phi)
    assert quality.candle_quality_observables(events)['coplanarity_deg'][0] == pytest.approx(expected, abs=1e-12)


def test_pi0_shape_fit_uses_shared_gaussian_fitter():
    values = np.random.default_rng(883).normal(.135, .007, 20000)
    fit = quality._mass_fit(values, (.10, .17))
    assert fit['status'] == 'ok'
    assert fit['mean_gev'] == pytest.approx(.135, abs=.0003)
    assert fit['sigma_gev'] == pytest.approx(.007, abs=.0003)
    assert fit['window_gev'] == [.10, .17]
    assert 'not detector resolution' in fit['interpretation']


def test_missing_raw_vectors_and_nonfinite_vectors_fail_explicitly():
    with pytest.raises(ValueError, match='raw target'):
        quality.candle_quality_observables(replace(_events(), target=None))
    events = _events()
    events.proton[0, 0] = np.nan
    with pytest.raises(ValueError, match='non-finite'):
        quality.candle_quality_observables(events)


def test_report_counts_all_events_and_normalizes_only_defined_values(tmp_path):
    events = _events()
    samples = {'raw_bdt': events, 'raw_bdt_core': events.take(np.array([True, False, False])),
               'raw_bdt_tails': events.take(np.array([False, True, True]))}
    report = quality.write_candle_quality_report(tmp_path, samples)
    assert report == json.loads((tmp_path / 'quality_audit.json').read_text())
    assert report['additional_plot_cuts'] == []
    assert report['samples']['raw_bdt']['event_count'] == 3
    for key, expected in [('eta_mass_gev', 2), ('pi0_mass_gev', 3),
                          ('missing_mass_gev', 3), ('coplanarity_deg', 1),
                          ('theta_missing_proton_deg', 2)]:
        audit = report['samples']['raw_bdt']['histograms'][key]
        assert audit['finite_count'] == expected
        assert audit['nonfinite_count'] == 3 - expected
        assert sum(audit['counts']) == expected
        edges = np.array(report['histogram_edges'][key])
        assert np.dot(audit['density'], np.diff(edges)) == pytest.approx(1.)
    plane = report['samples']['raw_bdt']['beam_energy_vs_proton_theta']
    assert plane['finite_count'] == 2
    assert np.sum(plane['counts']) == 2
    plane_edges = report['beam_energy_vs_proton_theta_edges']
    area = np.diff(plane_edges['theta_deg'])[:, None] * np.diff(plane_edges['energy_gev'])[None, :]
    assert np.sum(np.asarray(plane['density']) * area) == pytest.approx(1.)
    assert report['samples']['raw_bdt']['undefined_angles']['coplanarity_deg'] == 2
    for filename in report['pdf_files']:
        assert (tmp_path / filename).read_bytes().startswith(b'%PDF')


def test_empty_samples_do_not_fake_resolution_or_density(tmp_path):
    empty = _events().take(np.zeros(3, dtype=bool))
    report = quality.write_candle_quality_report(tmp_path, {'raw_bdt': empty})
    sample = report['samples']['raw_bdt']
    assert sample['event_count'] == 0
    assert sample['mass_fits']['eta_mass_gev']['status'] == 'insufficient_data'
    assert sample['mass_fits']['pi0_mass_gev']['status'] == 'insufficient_data'
    assert sum(sample['histograms']['missing_mass_gev']['density']) == 0.
