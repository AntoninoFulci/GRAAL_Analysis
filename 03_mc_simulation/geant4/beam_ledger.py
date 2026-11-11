"""Bind unsmeared incident energies and unit weights to native ROOT replay.

The all-event denominator is the exported generator cohort, including events with
no detector hits. Native input identity and recorded primaries prove the binding;
matching event counts alone never authorize attaching generator information.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import numpy as np
import uproot

from mc_simulation.geant4.central import sha256
from mc_simulation.geant4.tagger import _table
from mc_simulation.geant4.trigger import _strict_json
from mc_simulation.geant4.root_output import read_transport_summary

WEIGHT_POLICY = 'unit_unweighted_no_flux_or_cross_section_normalization'
BEAM_TYPES = dict(run='int32', event='int32', source_entry='uint64',
                  energy_GeV='float64', generation_weight='float64')


def _require(value, message):
    if not value:
        raise ValueError(message)


def _watch(path, digest, watched):
    _require(isinstance(path, str) and Path(path).is_absolute(), 'Source path must be absolute')
    _require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Invalid source SHA256')
    path = Path(path).resolve(strict=True)
    _require(sha256(path) == digest, f'Immutable source SHA256 mismatch: {path}')
    watched[path] = digest
    return path


def _stable(watched):
    for path, digest in watched.items():
        _require(sha256(path) == digest, f'Immutable input changed before publication: {path}')


def _count(meta, name):
    value = meta.get(name)
    _require(type(value) is int and 0 <= value <= 2**63-1, f'Invalid count: {name}')
    return value


def _ordered(rows, count):
    _require(len(rows['event']) == count and np.array_equal(rows['event'], np.arange(count))
             and ('run' not in rows or np.all(rows['run'] == 0))
             and ('source_entry' not in rows or np.array_equal(rows['source_entry'], np.arange(count))),
             'Complete ordered single-run event ledger required')


def _binding(transport, truth, watched):
    from mc_simulation.geant4.export_truth import validate_root_truth

    validate_root_truth(truth)
    with uproot.open(truth) as root:
        meta = _strict_json(root, 'metadata')
        ev = _table(root, 'events', dict(event='int32', source_entry='uint64', energy_GeV='float64',
                                        generation_weight='float64', nprimaries='int32'))
        prim = _table(root, 'primaries', dict(event='int32', primary_index='int32', pdg='int32',
                     **{k: 'float64' for k in ('px_GeV', 'py_GeV', 'pz_GeV', 'energy_GeV', 'mass_GeV')}))
    count = _count(meta, 'events')
    _require(count > 0 and _count(meta, 'source_events') >= count, 'Invalid generator denominator')
    _ordered(ev, count)
    _require(meta.get('weight_policy') == WEIGHT_POLICY and np.all(ev['generation_weight'] == 1.),
             'Only explicit unit-unweighted generation weights are supported')
    _watch(meta['source'], meta['source_sha256'], watched)
    with uproot.open(transport) as root:
        summary = read_transport_summary(root)
        _require(summary.get('status') == 'diagnostic_transport_only'
                 and summary.get('source_mode') == 'root_replay'
                 and summary.get('output_format') == 'ROOT_TTree',
                 'Complete native ROOT replay transport required')
        _require(_count(summary, 'events') == _count(summary, 'attempted_events') == count
                 and _count(summary, 'aborted') == 0, 'Transport/export event conservation mismatch')
        source = _table(root, 'events', dict(run='int32', event='int32', aborted='int32'))
        _ordered(source, count)
        _require(np.all(source['aborted'] == 0), 'Aborted replay events are unsupported')
        with truth.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'md5').hexdigest()
        _require(summary.get('replay_input_path') == str(truth)
                 and summary.get('replay_input_md5') == digest
                 and str(root['input_source']) == str(truth) and str(root['input_md5']) == digest,
                 'Native replay input identity does not match truth ROOT')
        actual = _table(root, 'primaries', dict(run='int32', event='int32', vertex='int32',
                        particle='int32', pdg='int32', **{k: 'float64' for k in
                        ('vertex_weight', 'particle_weight', 'px_MeV', 'py_MeV', 'pz_MeV', 'kinetic_MeV')}))
    _require(np.array_equal(actual['event'], prim['event']) and np.all(actual['run'] == 0)
             and np.all(actual['vertex'] == 0) and np.array_equal(actual['particle'], prim['primary_index'])
             and np.array_equal(actual['pdg'], prim['pdg']), 'Native replay primary identities mismatch')
    for axis in ('px', 'py', 'pz'):
        _require(np.allclose(actual[axis+'_MeV'], prim[axis+'_GeV']*1000., rtol=1e-12, atol=1e-9),
                 'Native replay primary momentum mismatch')
    _require(np.all(actual['vertex_weight'] == 1.) and np.all(actual['particle_weight'] == 1.),
             'Native replay primary weights mismatch')
    # GEANT4 and the generator proton masses differ by a few eV. Preserve that
    # established transport convention while detecting a different kinetic state.
    _require(np.allclose(actual['kinetic_MeV'], (prim['energy_GeV']-prim['mass_GeV'])*1000.,
                        rtol=1e-10, atol=1e-5), 'Native replay primary kinetic energy mismatch')
    return ev, meta, summary


def bind_beam_ledger(transport_root, truth_root, output_root, *, run_manifest=None):
    """Publish a new native beam ROOT after proving its exact transported input."""
    output = Path(os.path.abspath(output_root))
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing to overwrite beam ledger: {output}')
    transport, truth = (Path(p).resolve(strict=True) for p in (transport_root, truth_root))
    watched = {p: sha256(p) for p in (transport, truth)}
    events, truth_meta, summary = _binding(transport, truth, watched)
    manifest = None
    if run_manifest is not None:
        manifest = Path(run_manifest).resolve(strict=True)
        watched[manifest] = sha256(manifest)
        with manifest.open() as stream:
            run = json.load(stream)
        _require(run.get('truth_root_sha256') == watched[truth], 'Launcher truth SHA256 mismatch')
    count = len(events['event'])
    meta = dict(schema=1, role='incident_beam_response_input', transport_path=str(transport),
                transport_sha256=watched[transport], truth_path=str(truth), truth_sha256=watched[truth],
                source_sha256={str(p): digest for p, digest in watched.items()},
                source_events=truth_meta['source_events'], events=count, exported_events=count,
                weight_policy=WEIGHT_POLICY, units='GeV', sumw=float(count), sumw2=float(count),
                source_identity=truth_meta, native_replay_summary=summary,
                run_manifest_path=str(manifest) if manifest else None,
                binding_policy='native_input_path_md5_and_recorded_primaries_with_immutable_sha256',
                physical_validation=False, physics_validation=False, efficiency_validation=False)
    values = dict(run=np.zeros(count, dtype='int32'), **{k: events[k] for k in BEAM_TYPES if k != 'run'})
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f'.{output.name}.', suffix='.pending', dir=output.parent)
    os.close(descriptor)
    try:
        with uproot.recreate(temporary) as root:
            root.mktree('beam_events', BEAM_TYPES).extend(values)
            root['metadata'] = json.dumps(meta, sort_keys=True, allow_nan=False)
        _stable(watched)
        os.link(temporary, output)  # Exclusive publication; cannot replace another writer.
    finally:
        Path(temporary).unlink(missing_ok=True)
    return output


def read_beam_ledger(ledger_root, *, transport_root):
    """Revalidate binding, all immutable sources, and every generator denominator row.

    Returns (native arrays, metadata, watched Path -> SHA256 mapping), allowing
    callers to check immutability again immediately before publishing their output.
    """
    ledger, transport = (Path(p).resolve(strict=True) for p in (ledger_root, transport_root))
    watched = {ledger: sha256(ledger), transport: sha256(transport)}
    with uproot.open(ledger) as root:
        meta = _strict_json(root, 'metadata')
        values = _table(root, 'beam_events', BEAM_TYPES)
    _require(meta.get('role') == 'incident_beam_response_input'
             and meta.get('transport_path') == str(transport)
             and meta.get('transport_sha256') == watched[transport], 'Beam ledger transport identity mismatch')
    sources = meta.get('source_sha256')
    _require(isinstance(sources, dict) and bool(sources), 'Missing beam source SHA256 provenance')
    for path, digest in sources.items():
        _watch(path, digest, watched)
    truth = _watch(meta['truth_path'], meta['truth_sha256'], watched)
    _require(sources.get(str(truth)) == watched[truth] and sources.get(str(transport)) == watched[transport],
             'Missing beam transport/truth source identity')
    expected, truth_meta, summary = _binding(transport, truth, watched)
    count = len(expected['event'])
    _ordered(values, count)
    _require(meta.get('weight_policy') == WEIGHT_POLICY and np.all(values['generation_weight'] == 1.),
             'Only explicit unit-unweighted generation weights are supported')
    for key in ('event', 'source_entry', 'energy_GeV', 'generation_weight'):
        _require(np.array_equal(values[key], expected[key]), f'Beam ledger differs from transported truth: {key}')
    _require(meta.get('source_identity') == truth_meta and meta.get('native_replay_summary') == summary
             and sources.get(truth_meta['source']) == truth_meta['source_sha256'], 'Beam source identity mismatch')
    _require(_count(meta, 'events') == _count(meta, 'exported_events') == count
             and _count(meta, 'source_events') == truth_meta['source_events']
             and meta.get('sumw') == count and meta.get('sumw2') == count, 'Beam denominator statistics mismatch')
    _require(all(meta.get(flag) is False for flag in ('physical_validation', 'physics_validation', 'efficiency_validation')),
             'Beam ledger must remain diagnostic')
    _stable(watched)
    return values, meta, watched
