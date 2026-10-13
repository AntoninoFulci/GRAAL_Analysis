from pathlib import Path
import numpy as np
from calibration.run_manifest import RunRecord, write_manifest


def audit_inputs(tmp_path, *, missing=(), duplicate=None, negative=False):
    import ROOT
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(7, '1998_uv', 'P', 'UV', 'P_UV', 'manual', '1998_uv/run7.root')], manifest)
    raw = tmp_path / 'raw.root'
    output = ROOT.TFile(str(raw), 'RECREATE')
    for state in ('POL1', 'POL2', 'BREM'):
        if state in missing: continue
        hist = ROOT.TH1D(f'run7_{state}', '', 128, 0, 128)
        for strip in range(1, 129): hist.SetBinContent(strip, 0 if state == 'BREM' else 10)
        if negative and state == 'POL1': hist.SetBinContent(1, -1)
        hist.Write()
        if state == duplicate: hist.Write()
    output.Close()
    cal = tmp_path / 'cal.root'
    ROOT.TFile(str(cal), 'RECREATE').Close()
    return dict(manifest=manifest, raw_flux=raw, calibrated_flux=cal)


def study_audit(n=36):
    metadata, histograms = {}, {}
    for run in range(1, n + 1):
        for si, state in enumerate(('POL1', 'POL2', 'BREM')):
            key = (run, state)
            metadata[key] = dict(run_number=run, state=state, source_period='1998_uv', target='P', beam_type='UV', configuration_id='A', laser_id='UV', start=float(run*100+si*10), end=float(run*100+si*10+5), exposure=None, experiment_group=None)
            values = np.ones(128); values[:10] += run * .02 + si * .03
            histograms[key] = values * (10 + si)
    return dict(schema_version=1, inputs={}, summary={}, rows=[], strips=[], metadata=metadata, histograms=histograms)
