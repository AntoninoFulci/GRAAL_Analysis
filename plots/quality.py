"""Physical controls of completed raw reconstructions, without new cuts."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import ROOT


def fit_eta_mass(histogram) -> dict:
    """Diagnostic Gaussian in 0.50..0.60 GeV; never changes the input histogram."""
    result = {'window_gev': [0.50, 0.60], 'model': 'gaus', 'status': 'insufficient_data'}
    bins = [i for i in range(1, histogram.GetNbinsX() + 1)
            if 0.50 <= histogram.GetBinCenter(i) <= 0.60 and histogram.GetBinContent(i) > 0]
    if len(bins) <= 3:
        return result
    # N avoids attaching an unnormalised fit to the later unit-area clones.
    fit = histogram.Fit('gaus', 'SQ0N', '', 0.50, 0.60)
    result.update(status='failed', fit_status=int(fit))
    if int(fit) != 0 or not fit.IsValid():
        return result
    values = [fit.Parameter(1), fit.Parameter(2), fit.ParError(1), fit.ParError(2), fit.Chi2()]
    if not np.all(np.isfinite(values)) or values[1] <= 0:
        return result
    result.update(status='ok', mean_gev=float(values[0]), sigma_gev=float(values[1]),
                  mean_error_gev=float(values[2]), sigma_error_gev=float(values[3]),
                  chi2=float(values[4]), ndf=int(fit.Ndf()),
                  covariance_status=int(fit.CovMatrixStatus()))
    return result


def render(samples: dict, mass_histograms: dict, out_dir: Path) -> tuple[dict, dict]:
    """Render controls using detached adapter arrays; return ROOT products/metadata."""
    ROOT.gROOT.SetBatch(True)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    definitions = (
        ('theta_missing_proton', 'theta_missing_proton_deg',
         '#theta_{missing}-#theta_{proton} [deg]', -10., 10.),
        ('coplanarity', 'coplanarity_deg',
         '#Delta#phi(p,#eta#pi^{0})-180#circ (wrapped) [deg]', -10., 10.),
        ('missing_mass', 'missing_mass_gev',
         'M(beam+target-#eta-#pi^{0}) [GeV]', .8, 1.1),
    )
    histograms = {}
    metadata = {
        'schema': 1,
        'definitions': {
            'theta_missing_proton_deg': 'theta(missing branch)-theta(measured proton), degrees',
            'coplanarity_deg': 'wrap(phi(measured proton)-phi(eta+pi0)-180 deg) in [-180,180)',
            'missing_mass_gev': 'signed sqrt((beam+target-eta-pi0)^2), TLorentzVector.M convention',
            'beam_energy_vs_proton_theta': 'measured proton theta [deg], beam energy [GeV]',
        },
        'additional_plot_cuts': [],
        'undefined_direction_policy': 'zero momentum: undefined theta; zero transverse momentum: undefined phi; omit only affected angle, count per sample',
        'interpretation': 'unit event counts after reconstruction selection, including existing missing-mass cut; no flux or acceptance correction; Gaussian fit is diagnostic only',
        'samples': {},
    }
    for tag, data in samples.items():
        controls = data.quality
        metadata['samples'][tag] = {
            'undefined_angles': {key: int(np.count_nonzero(~np.isfinite(controls[key])))
                                 for key in ('theta_missing_proton_deg', 'coplanarity_deg', 'proton_theta_deg')},
            'eta_mass_fit': fit_eta_mass(mass_histograms[f'massa_eta_{tag}']),
        }
        for stem, key, axis, low, high in definitions:
            name = f'{stem}_{tag}'
            h = ROOT.TH1D(name, f'{tag};{axis};eventi', 100, low, high)
            h.SetDirectory(0)
            h.SetStats(False)
            for value in controls[key][np.isfinite(controls[key])]:
                h.Fill(float(value))
            histograms[name] = h
        name = f'beam_energy_vs_proton_theta_{tag}'
        h = ROOT.TH2D(name, f'{tag};#theta_{{proton}} [deg];E_{{#gamma}} [GeV]',
                      50, 0., 40., 50, .9, 1.55)
        h.SetDirectory(0)
        h.SetStats(False)
        h.GetZaxis().SetTitle('eventi / bin')
        valid = np.isfinite(controls['proton_theta_deg'])
        for angle, energy in zip(controls['proton_theta_deg'][valid], data.beam_energy[valid]):
            h.Fill(float(angle), float(energy))
        histograms[name] = h

    labels = {'chi2': 'solo chi2', 'bdt': 'gate BDT'}
    for stem, _, _, _, _ in definitions:
        canvas = ROOT.TCanvas(f'c_quality_{stem}', stem, 900, 700)
        try:
            canvas.SetLeftMargin(.14)
            canvas.SetBottomMargin(.14)
            legend = ROOT.TLegend(.60, .73, .89, .89)
            maximum = max(histograms[f'{stem}_{tag}'].GetMaximum() for tag in samples)
            for i, tag in enumerate(samples):
                h = histograms[f'{stem}_{tag}']
                h.SetTitle('controllo fisico dopo la selezione')
                h.SetLineColor(ROOT.kGray + 2 if tag == 'chi2' else ROOT.kAzure + 1)
                h.SetLineWidth(2)
                h.SetMaximum(max(1., maximum) * 1.2)
                h.Draw('hist' if i == 0 else 'hist same')
                legend.AddEntry(h, labels[tag], 'l')
            legend.Draw()
            canvas.SaveAs(str(out_dir / f'{stem}.pdf'))
        finally:
            canvas.Close()

    stem = 'beam_energy_vs_proton_theta'
    canvas = ROOT.TCanvas(f'c_quality_{stem}', stem, 1400, 650)
    try:
        canvas.Divide(len(samples), 1)
        maximum = max(histograms[f'{stem}_{tag}'].GetMaximum() for tag in samples)
        for i, tag in enumerate(samples, 1):
            canvas.cd(i)
            ROOT.gPad.SetLeftMargin(.14)
            ROOT.gPad.SetRightMargin(.16)
            ROOT.gPad.SetBottomMargin(.14)
            h = histograms[f'{stem}_{tag}']
            h.SetTitle(labels[tag])
            h.SetMinimum(0.)
            h.SetMaximum(max(1., maximum))
            h.Draw('colz')
        canvas.SaveAs(str(out_dir / f'{stem}.pdf'))
    finally:
        canvas.Close()
    return histograms, metadata
