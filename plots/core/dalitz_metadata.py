"""Provenance and population accounting for the Dalitz ROOT product."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import numpy as np
import ROOT

from calibration.run_manifest import validate_manifest
from reconstruction.runtime.provenance import file_identities, validate_reconstruction_selection
from plots.core import kinematics as kin

DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / 'config/support/run_manifest.csv'


def read_provenance(source, tree) -> dict:
    return validate_reconstruction_selection(source, tree)


def compare_selections(chi2: dict | None, bdt: dict | None) -> str:
    """Reject different raw selection contracts."""
    if not chi2 or not bdt:
        return 'unknown_incomplete_comparison_provenance'
    for field in ('input_tree', 'channel'):
        if chi2.get(field) and bdt.get(field) and chi2[field] != bdt[field]:
            raise ValueError(f'Dalitz selection mismatch: {field}')
    if not all(isinstance(record.get('selection'), dict) for record in (chi2, bdt)):
        return 'unknown_incomplete_comparison_provenance'
    selections = [{k: v for k, v in record['selection'].items() if k != 'bdt_threshold'}
                  for record in (chi2, bdt)]
    if selections[0] != selections[1] or chi2.get('channel') != bdt.get('channel'):
        raise ValueError('Dalitz selection mismatch between chi2 and BDT inputs')
    if 'inputs' in chi2 and 'inputs' in bdt:
        identities = [{(item['sha256'], item['size']) for item in record['inputs']}
                      for record in (chi2, bdt)]
        if identities[0] != identities[1]:
            raise ValueError('Dalitz selection comparison requires the same source inputs')
    required_cuts = {'chi2_cut', 'chi2_resolution_relative', 'energy_range_gev',
                     'missing_mass_window_gev', 'partner_mass_gev', 'photons', 'protons'}
    if any(not record.get('inputs') or not record.get('input_tree') or not record.get('channel')
           or not required_cuts.issubset(record['selection'])
           for record in (chi2, bdt)):
        return 'unknown_incomplete_comparison_provenance'
    return 'matched_except_bdt_gate'


def _range(values):
    return [float(np.min(values)), float(np.max(values))] if len(values) else None


def build_metadata(args, samples: dict, provenance: dict, comparison: str, command: list) -> dict:
    repo = Path(__file__).resolve().parents[2]
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repo,
                              capture_output=True, text=True, check=False).stdout.strip()
    manifest = args.run_manifest
    records = {r.run_number: r for r in validate_manifest(manifest)} if manifest.is_file() else {}
    result = {
        'schema': 1, 'command': command, 'source_revision': revision or None,
        'source_files': file_identities([repo/'plots/dalitz.py', Path(__file__),
                                         repo/'plots/core/kinematics.py',
                                         repo/'plots/core/reconstruction_data.py',
                                         repo/'00_common/physics/channels.py',
                                         repo/'plots/quality.py']),
        'versions': {'python': sys.version, 'numpy': np.__version__, 'ROOT': ROOT.gROOT.GetVersion()},
        'manifest': file_identities([manifest])[0] if manifest.is_file() else None,
        'masses_gev': {'proton': kin.M_PROTON, 'eta': kin.M_ETA, 'pi0': kin.M_PI0},
        'selection_comparison': comparison,
        'additional_plot_cuts': [], 'event_weight': 1,
        'normalization': {'yield': 'unit event counts; no flux or acceptance correction',
                          'unit_area': 'divide by yield including all under/overflow cells; fraction per bin',
                          'empty': 'zero bins; unit-area normalization undefined',
                          'density': 'M and signed M² filled independently; no density transformation'},
        'residual_definition': 's_peta+s_ppi0+s_etapi0-W_event^2-mp^2-meta^2-mpi0^2 [GeV^2]',
        'boundary': 'no boundary cut or mean-W curve; over_limit counts only M(p eta)>W_event-mpi0',
        'implicit_proton': 'missing-mass diagnostic, not independent recoil measurement',
        'samples': {},
    }
    for tag, data in samples.items():
        runs = None if data.run_numbers is None else sorted(map(int, np.unique(data.run_numbers)))
        known = [records[run] for run in (runs or []) if run in records]
        periods = sorted({r.source_period for r in known})
        profiles = sorted({r.beam_type.lower() for r in known})
        profile = args.profile or (profiles[0] if len(profiles) == 1 else None)
        if args.profile and profiles and profiles != [args.profile]:
            raise ValueError('declared profile disagrees with observed run manifest')
        prov = provenance[tag]
        result['samples'][tag] = {
            'sample': 'raw' + ('_bdt' if tag == 'bdt' else ''),
            'profile': profile, 'profile_source': 'argument' if args.profile else 'run_manifest',
            'periods': periods or None, 'runs': runs,
            'unmapped_runs': None if runs is None else [r for r in runs if r not in records],
            'input': file_identities([getattr(args, tag)])[0],
            'reconstruction_provenance': prov,
            'selection_energy_range_gev': (prov or {}).get('selection', {}).get('energy_range_gev'),
            'observed_energy_range_gev': _range(data.beam_energy),
            'observed_w_range_gev': _range(data.w),
            'entries': len(data.eta_mass),
            'over_limit_count': int(np.count_nonzero(data.over_limit)),
            'eta_over_beam_count': int(np.count_nonzero(data.eta_over_beam)),
            'residuals_gev2': {mode: {'range': _range(values),
                                    'mean': float(np.mean(values)) if len(values) else None}
                              for mode, values in data.identity_residual.items()},
        }
    return result
