"""Physical controls exercise real ROOT histograms and fits."""
import json

import numpy as np
import pytest
import ROOT

from plots.core import reconstruction_data
from plots.tests.test_reconstruction_data import _event, _Tree, _Vector


def test_quality_histograms_count_flows_and_undefined_angles(tmp_path):
    from plots import quality
    event = _event()
    event.eta = _Vector(0.2, 0., 0., 0.55)
    event.pi0 = _Vector(0.1, 0., 0., 0.14)
    event.proton = _Vector(-0.3, 0., 0.4, 0.99)
    event.missing = _Vector(-0.3, 0., 1.5, 1.75)
    data = reconstruction_data.collect(_Tree([event, _event()]))
    masses = {f'massa_eta_{tag}': ROOT.TH1D(f'test_eta_{tag}', '', 100, .3, .8)
              for tag in ('chi2', 'bdt')}
    histograms, metadata = quality.render({'chi2': data, 'bdt': data}, masses, tmp_path)
    polar = histograms['theta_missing_proton_bdt']
    assert polar.GetEntries() == 1
    assert polar.Integral() == 0  # finite polar residual lies below -10 degrees
    assert polar.GetBinContent(0) == 1
    assert histograms['coplanarity_bdt'].Integral() == 1
    assert histograms['coplanarity_bdt'].GetMean() == pytest.approx(0.)
    assert histograms['missing_mass_bdt'].GetEntries() == 2
    assert histograms['beam_energy_vs_proton_theta_bdt'].GetEntries() == 1
    assert histograms['beam_energy_vs_proton_theta_bdt'].GetYaxis().GetTitle() == 'E_{#gamma} [GeV]'
    counts = metadata['samples']['bdt']['undefined_angles']
    assert counts == {'theta_missing_proton_deg': 1, 'coplanarity_deg': 1, 'proton_theta_deg': 1}
    json.dumps(metadata, allow_nan=False)
    for stem in ('theta_missing_proton', 'coplanarity', 'missing_mass', 'beam_energy_vs_proton_theta'):
        assert (tmp_path / f'{stem}.pdf').read_bytes().startswith(b'%PDF')


@pytest.mark.parametrize('count', [0, 1])
def test_eta_fit_explicitly_skips_empty_or_sparse_histogram(count):
    from plots import quality
    histogram = ROOT.TH1D(f'eta_sparse_{count}', '', 100, .3, .8)
    for _ in range(count):
        histogram.Fill(.55)
    result = quality.fit_eta_mass(histogram)
    assert result['status'] == 'insufficient_data'
    assert 'mean_gev' not in result
    assert result['window_gev'] == [.50, .60]


def test_eta_gaussian_fit_records_parameters_without_mutating_histogram():
    from plots import quality
    histogram = ROOT.TH1D('eta_gaussian_test', '', 100, .3, .8)
    rng = np.random.default_rng(20261029)
    for value in rng.normal(.548, .012, 5000):
        histogram.Fill(value)
    result = quality.fit_eta_mass(histogram)
    assert result['status'] == 'ok'
    assert result['mean_gev'] == pytest.approx(.548, abs=.001)
    assert result['sigma_gev'] == pytest.approx(.012, abs=.001)
    assert result['covariance_status'] == 3
    assert not histogram.GetFunction('gaus')
    assert histogram.GetEntries() == 5000
    json.dumps(result, allow_nan=False)


def test_quality_empty_samples_still_produce_empty_controls(tmp_path):
    from plots import quality
    data = reconstruction_data.collect(_Tree([]))
    masses = {f'massa_eta_{tag}': ROOT.TH1D(f'empty_eta_{tag}', '', 100, .3, .8)
              for tag in ('chi2', 'bdt')}
    hists, metadata = quality.render({'chi2': data, 'bdt': data}, masses, tmp_path)
    assert all(h.GetEntries() == 0 for h in hists.values())
    assert metadata['samples']['chi2']['eta_mass_fit']['status'] == 'insufficient_data'


def test_eta_fit_failure_does_not_publish_parameters(monkeypatch):
    from plots import quality
    histogram = ROOT.TH1D('eta_failed_test', '', 100, .3, .8)
    for mass in (.512, .532, .552, .572):
        histogram.Fill(mass)
    # Inject a minimizer failure at the ROOT boundary, keeping bin accounting real.
    monkeypatch.setattr(histogram, 'Fit', lambda *args: 4)
    result = quality.fit_eta_mass(histogram)
    assert result['status'] == 'failed'
    assert result['fit_status'] == 4
    assert 'mean_gev' not in result
