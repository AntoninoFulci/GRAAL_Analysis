"""Measured detector products to minimal native h70 plus an all-event ledger.

This is a diagnostic input bridge, not calibrated reconstruction or efficiency.
Historical producer source/executable hashes are retained without requiring an
obsolete build to remain installed. Immutable measured inputs/configs are checked.
"""
from array import array
import csv
import json
import os
from pathlib import Path
import re

import numpy as np
import uproot

from mc_simulation.geant4.central import sha256, _write_provenance
from mc_simulation.geant4.trigger import _strict_json
from mc_simulation.geant4.root_output import read_transport_summary
from graal_common.io.filesystem import atomic_output_directory

REPO = Path(__file__).resolve().parents[2]
MODE = 'measured_h70_diagnostic'
REASONS = dict(central_unavailable=1, forward_unavailable=2, tagger_unavailable=4,
               trigger_unavailable=8, trigger_rejected=16)
KEYS = dict(run='int32', event='int32')
EVENT_KEYS = dict(KEYS, source_entry='uint64')


def validate_acquisition(period, acquisition_run, polarization):
    if (not isinstance(period, str) or not re.fullmatch(r'[A-Za-z0-9_]+', period)
            or type(acquisition_run) is not int or not 0 < acquisition_run <= 2**32-1
            or type(polarization) is not int or polarization not in (0, 1, 2)):
        raise ValueError('Explicit valid period, acquisition run and polarization 0/1/2 required')
    with (REPO / 'config/support/run_manifest.csv').open(newline='') as stream:
        rows = [r for r in csv.DictReader(stream) if int(r['run_number']) == acquisition_run]
    if len(rows) != 1 or rows[0]['source_period'] != period:
        raise ValueError('Acquisition run does not match repository period mapping')
    return rows[0]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)


def _watch(path, expected, watched):
    _require(_digest(expected), 'Missing immutable SHA256 identity')
    path = Path(path).resolve(strict=True)
    _require(sha256(path) == expected, f'Immutable input SHA256 mismatch: {path}')
    watched[path] = expected
    return path


def _integer(obj, name, maximum=2**64-1):
    value = obj.get(name)
    _require(type(value) is int and 0 <= value <= maximum, f'Invalid integer metadata: {name}')
    return value


def _table(root, name, fields):
    tree = root[name]
    _require(tree.classname == 'TTree', f'{name} must be a native TTree')
    result = {}
    for key, dtype in fields.items():
        branch = tree[key]
        value = branch.array(library='np')
        _require(value.ndim == 1 and len(value) == tree.num_entries,
                 f'Invalid scalar cardinality: {name}.{key}')
        if dtype == 'string':
            _require(all(isinstance(x, str) and '\0' not in x for x in value), f'Invalid string: {key}')
        else:
            _require(value.dtype == np.dtype(dtype), f'Wrong native branch type: {name}.{key}')
            leaves = branch.member('fLeaves')
            _require(len(leaves) == 1 and leaves[0].member('fLen') == 1
                     and leaves[0].member('fLeafCount') is None, f'Not a scalar leaf: {key}')
        result[key] = value
    return result


def _keys(rows):
    return list(zip(rows['run'].tolist(), rows['event'].tolist()))


def _ledger(rows, source):
    _require(_keys(rows) == _keys(source), 'Event ledgers are not identical and ordered')
    if 'source_entry' in rows:
        _require(np.array_equal(rows['source_entry'], np.arange(len(source['run']))),
                 'Wrong source_entry event ledger')


def _range(values, low, high, label):
    _require(np.all(np.isfinite(values)) and np.all(values >= low) and np.all(values <= high),
             f'Invalid finite/range values: {label}')


def _objects(root, name, fields, source, index, counts):
    rows = _table(root, name, dict(KEYS, **fields))
    locations = {key: i for i, key in enumerate(_keys(source))}
    grouped = [[] for _ in locations]
    last = -1
    for j, key in enumerate(_keys(rows)):
        _require(key in locations and locations[key] >= last, f'Orphan/reordered {name}')
        last = locations[key]
        _require(int(rows[index][j]) == len(grouped[last]), f'Noncontiguous {name} index')
        grouped[last].append(j)
    _require([len(v) for v in grouped] == [int(v) for v in counts], f'{name} count mismatch')
    return rows, grouped


def _producer(path, transport, watched, kind):
    path = Path(path).resolve(strict=True)
    watched[path] = sha256(path)
    manifest = path.with_name('provenance.root')
    watched[manifest] = sha256(manifest)
    with uproot.open(manifest) as f:
        provenance = _strict_json(f, 'metadata')
    result_hash = 'response_sha256' if kind == 'forward' else 'result_sha256'
    _require(provenance.get(result_hash) == watched[path], f'{kind} result/provenance SHA256 mismatch')
    path_key, hash_key = ('input_path', 'input_sha256') if kind == 'forward' else ('transport_path', 'transport_sha256')
    _require(_watch(provenance[path_key], provenance[hash_key], watched) == transport,
             f'{kind} uses a different immutable transport')
    hashes = provenance.get('code_sha256')
    _require(isinstance(hashes, dict) and bool(hashes) and all(isinstance(k, str) and _digest(v)
             for k, v in hashes.items()), f'Missing {kind} historical producer code hashes')
    with uproot.open(path) as f:
        metadata = _strict_json(f, 'metadata')
        if kind in ('central', 'forward'):
            selected = _strict_json(f, 'config_metadata')
            summary = _strict_json(f, 'summary')
            expected = f'selected26_{kind}_reconstruction_diagnostic'
            _require(all(item.get('mode') == expected for item in (metadata, provenance)), 'Producer mode mismatch')
            _require(summary == provenance.get('summary') and summary.get('status') == f'selected26_{kind}_diagnostic_complete', 'Producer completion mismatch')
            _integer(summary, 'events')
            _require(all(item.get('physical_validation') is False and item.get('physics_validation') is False
                         for item in (metadata, provenance, summary)), 'Invalid diagnostic validation flags')
            config_key = 'configuration_path' if kind == 'central' else 'config_path'
            if kind == 'central':
                inputs = provenance.get('input_sha256')
                _require(isinstance(inputs, dict) and bool(inputs), 'Missing central immutable input hashes')
                for p, digest in inputs.items():
                    _require(_digest(digest), 'Malformed central input hash')
                    if p != provenance.get('executable_path'):
                        _watch(p, digest, watched)
                config = Path(provenance[config_key]).resolve(strict=True)
                _require(str(config) in inputs and inputs[str(config)] == sha256(config), 'Central config missing from immutable inputs')
                _require(provenance.get('configuration') == selected, 'Central configuration mismatch')
            else:
                config = _watch(provenance[config_key], provenance.get('config_sha256'), watched)
                _watch(provenance['tracking_path'], provenance.get('tracking_sha256'), watched)
                launcher = _strict_json(f, 'launcher_provenance')
                for key in ('input_path', 'input_sha256', 'tracking_sha256', 'executable_sha256', 'code_sha256', 'mode'):
                    _require(launcher.get(key) == provenance.get(key), f'Forward launcher mismatch: {key}')
            _require(Path(metadata['config_path']).resolve(strict=True) == config, 'Producer config path mismatch')
            with uproot.open(config) as cf:
                _require(_strict_json(cf, 'metadata') == selected, 'Immutable producer configuration mismatch')
        else:
            summary = _strict_json(f, 'summary') if 'summary' in f else None
    return path, metadata, provenance, summary


def _central(path, transport, source, watched, period, acquisition_run):
    path, meta, proof, summary = _producer(path, transport, watched, 'central')
    response = Path(proof['response_path']).resolve(strict=True)
    _require(Path(meta['response_path']).resolve(strict=True) == response, 'Central response path mismatch')
    _require(response in watched, 'Central response missing immutable input hash')
    with uproot.open(path) as f, uproot.open(response) as rf:
        response_meta = _strict_json(f, 'response_metadata')
        response_launcher = _strict_json(f, 'response_launcher_provenance')
        _require(response_meta == _strict_json(rf, 'metadata') and
                 response_launcher == _strict_json(rf, 'launcher_provenance'), 'Central embedded response identity mismatch')
    _require(_integer(response_meta, 'historical_run', 2**31-1) == acquisition_run, 'Central response acquisition run mismatch')
    _require(response_meta.get('period') == period, 'Central response acquisition period mismatch')
    _require(_watch(response_launcher['input_path'], response_launcher.get('input_sha256'), watched) == transport, 'Central response transport mismatch')
    integers = ('association_available association_status bgo_status bgo_measurements_available '
                'barrel_input_available cylinder_input_available barrel_status associations '
                'good_bgo sp_bgo barrel_records cylinder_tracks ca_source_nero').split()
    with uproot.open(path) as f:
        ev = _table(f, 'central_events', dict(EVENT_KEYS, status='string', **{k:'int32' for k in integers}))
        _ledger(ev, source)
        _require(summary['events'] == len(ev['run']), 'Central summary event count mismatch')
        for key in ('association_available', 'bgo_measurements_available', 'barrel_input_available', 'cylinder_input_available'):
            _range(ev[key], 0, 1, key)
        _range(ev['ca_source_nero'], 0, 3, 'central CA source outcome')
        _range(ev['association_status'], -1, 63, 'association_status')
        _range(ev['bgo_status'], -1, 63, 'bgo_status')
        _require(np.array_equal(ev['bgo_measurements_available'], np.isin(ev['bgo_status'], [0,16])), 'Incoherent BGO availability')
        dependencies = ((ev['bgo_measurements_available'] == 1) & (ev['barrel_input_available'] == 1)
                        & (ev['cylinder_input_available'] == 1) & (ev['barrel_status'] == 0))
        _require(np.array_equal(ev['association_available'], dependencies), 'Incoherent central dependency availability')
        _require(np.array_equal(ev['association_status'] == -1, ~dependencies), 'Incoherent central status availability')
        ok = dependencies & (ev['association_status'] == 0)
        _range(ev['associations'], 0, 291, 'central associations capacity')
        _require(np.all(ev['associations'][~ok] == 0), 'Unavailable central event has associations')
        for key, maximum in [('good_bgo',480), ('sp_bgo',480), ('barrel_records',32), ('cylinder_tracks',5)]:
            _range(ev[key],0,maximum,key)
        _require(_integer(summary,'associations') == sum(map(int,ev['associations'])) and
                 _integer(summary,'unsupported_events') == int(np.count_nonzero(~ok)), 'Central summary counts mismatch')
        fields = {k:'int32' for k in ('association_index','bgo','barrel','cylinder','type')}
        fields.update({k:'float64' for k in ('bgo_energy_GeV','dedx_MeV','theta_deg','phi_deg')})
        rows, groups = _objects(f,'central_associations',fields,source,'association_index',ev['associations'])
    _range(rows['type'],1,30,'central type')
    for key in ('bgo_energy_GeV','dedx_MeV'):
        _range(rows[key],-1,np.finfo(np.float32).max,key)
        _require(np.all((rows[key]>=0)|(rows[key]==-1)), 'Invalid central missing-value sentinel')
    _range(rows['theta_deg'],-1,180,'central theta')
    _require(np.all((rows['theta_deg']>=0)|(rows['theta_deg']==-1)), 'Invalid central angle sentinel')
    _range(rows['phi_deg'],-360,360,'central phi')
    for i, group in enumerate(groups):
        expected = ('diagnostic_ca_rejected' if ev['ca_source_nero'][i] else 'diagnostic_objects' if group else 'diagnostic_no_object') if ok[i] else 'unsupported_central'
        _require(ev['status'][i] == expected, 'Invalid central status string')
        for key, count in [('bgo',ev['good_bgo'][i]+ev['sp_bgo'][i]),('barrel',ev['barrel_records'][i]),('cylinder',ev['cylinder_tracks'][i])]:
            _range(rows[key][group],0,int(count),'central source reference '+key)
    return ok, rows, groups, ev, response


def _forward(path, transport, source, watched, acquisition_run):
    path, meta, proof, summary = _producer(path,transport,watched,'forward')
    integers = ('planar_available wall_response_available shower_response_available wall_response_status '
                'shower_response_status wall_reconstruction_status shower_reconstruction_status association_status').split()
    with uproot.open(path) as f:
        selected = _strict_json(f, 'config_metadata')
        _require(isinstance(selected.get('reconstruction'), dict), 'Missing forward reconstruction configuration')
        _require(all(_integer(item, 'source_run', 65535) == acquisition_run for item in (meta, proof, selected['reconstruction'])), 'Forward acquisition source_run mismatch')
        ev = _table(f,'forward_events',dict(EVENT_KEYS,status='string',**{k:'int32' for k in integers},
                    **{k:'uint64' for k in ('particles','matches','wall_clusters','shower_clusters','planar_tracks')}))
        _ledger(ev,source)
        _require(summary['events']==len(ev['run']), 'Forward summary event mismatch')
        for key in ('planar_available','wall_response_available','shower_response_available'):
            _range(ev[key],0,1,key)
        for domain in ('wall','shower'):
            _range(ev[domain+'_response_status'],0,7,domain+' response status')
            _require(np.array_equal(ev[domain+'_response_available'],ev[domain+'_response_status']==0), 'Incoherent forward response availability')
            _range(ev[domain+'_reconstruction_status'],0,3,domain+' reconstruction status')
        _range(ev['association_status'],0,3,'forward association status')
        ok = ev['association_status']==0
        supported = (ev['planar_available']==1)&(ev['wall_response_available']==1)&(ev['shower_response_available']==1)&(ev['wall_reconstruction_status']==0)&(ev['shower_reconstruction_status']==0)
        _require(np.all(~ok|supported),'Valid forward association with unavailable inputs')
        for key in ('particles','matches'):
            _range(ev[key],0,90,key)
            _require(np.all(ev[key][~ok]==0),'Unavailable forward event has objects')
        _require(_integer(summary,'particles') == sum(map(int,ev['particles'])) and
                 _integer(summary,'unsupported_events') == int(np.count_nonzero(~ok)), 'Forward summary count mismatch')
        particles, groups = _objects(f,'forward_particles',dict(particle_index='uint64',source_match_index='int32',
                     **{k:'float64' for k in ('theta_deg','phi_deg','tof_ns','de_MeV')}),source,'particle_index',ev['particles'])
        matches, mgroups = _objects(f,'forward_matches',dict(match_index='uint64',mask='int32',planar='int32',wall='int32',shower='int32'),source,'match_index',ev['matches'])
        counts = _table(f,'forward_source_counts',dict(KEYS,strange='int32',wall_multiplicity_rejected='int32'))
        _ledger(counts,source)
    _range(counts['strange'],0,90,'strange count')
    _range(counts['wall_multiplicity_rejected'],0,1,'wall multiplicity rejected')
    _range(particles['theta_deg'],0,180,'forward theta')
    _range(particles['phi_deg'],-360,360,'forward phi')
    for name in ('tof_ns','de_MeV'):
        # Source timing may legitimately be negative; preserve measured values.
        _range(particles[name],-np.finfo(np.float32).max,np.finfo(np.float32).max,name)
    _range(matches['mask'],1,7,'forward association mask')
    for i,(group,mg) in enumerate(zip(groups,mgroups)):
        expected = ('diagnostic_wall_rejected' if counts['wall_multiplicity_rejected'][i]
                    else 'diagnostic_particles' if group else 'diagnostic_no_particle') if ok[i] else 'unsupported_forward'
        _require(ev['status'][i] == expected, 'Forward status string mismatch')
        _range(particles['source_match_index'][group],1,len(mg),'forward one-based source match')
        for key,capacity,bit in [('planar',ev['planar_tracks'][i],4),('wall',ev['wall_clusters'][i],2),('shower',ev['shower_clusters'][i],1)]:
            _range(matches[key][mg],0,int(capacity),'forward '+key+' reference')
            _require(np.array_equal((matches['mask'][mg]&bit)!=0,matches[key][mg]>0),'Forward mask/reference mismatch')
    return ok, particles, groups, matches, mgroups, counts['strange'], ev, counts


def _tagger(path, transport, source, watched, acquisition_run):
    size=len(source['run'])
    if path is None:
        return np.zeros(size,dtype=bool), {}, [[] for _ in range(size)]
    path,meta,proof,summary = _producer(path,transport,watched,'tagger')
    _require(meta.get('mode') == proof.get('mode') == 'legacy09_simulated_tagger_diagnostic', 'Invalid tagger mode')
    for item in (meta,proof):
        _require(_integer(item,'acquisition_run',2**32-1)==acquisition_run,'Tagger acquisition run mismatch')
        _require(item.get('transport_sha256')==watched[transport] and item.get('transport_path')==str(transport),'Tagger transport identity mismatch')
    _require(isinstance(summary,dict) and summary == proof.get('summary')
             and summary.get('status') == 'legacy09_simulated_tagger_diagnostic_complete'
             and summary.get('physics_validation') is False, 'Tagger completion summary mismatch')
    _require(_integer(summary,'events') == size, 'Tagger summary event count mismatch')
    _require(meta.get('configuration')==proof.get('configuration') and isinstance(proof.get('configuration'),dict), 'Tagger configuration mismatch')
    inputs=proof.get('input_sha256')
    _require(isinstance(inputs,dict) and bool(inputs),'Missing tagger immutable inputs')
    for p,digest in inputs.items():
        _watch(p,digest,watched)
    with uproot.open(path) as f:
        ev=_table(f,'tagger_events',dict(EVENT_KEYS,available='int32',nclusters='int32',status='int32'))
        _ledger(ev,source)
        _range(ev['available'],0,1,'tagger availability')
        _range(ev['status'],0,6,'tagger status')
        _range(ev['nclusters'],0,128,'tagger cluster capacity')
        available=ev['status']<=1
        _require(np.array_equal(ev['available'],available),'Tagger status/availability mismatch')
        _require(np.all(ev['nclusters'][ev['status']!=0]==0),'Unavailable/empty tagger has clusters')
        _require(np.all(ev['nclusters'][ev['status']==0]>0),'Accepted tagger has no clusters')
        rows,groups=_objects(f,'tagger_clusters',dict(cluster_index='int32',xstrip='float64',energy_GeV='float64',multiplicity='int32'),source,'cluster_index',ev['nclusters'])
    _require(_integer(summary,'available_events') == int(np.count_nonzero(available))
             and _integer(summary,'clusters') == len(rows['run']), 'Tagger summary count mismatch')
    _range(rows['xstrip'],1,128,'tagger mean strip index')
    _range(rows['energy_GeV'],0,np.finfo(np.float32).max,'tagger energy')
    _range(rows['multiplicity'],1,128,'tagger cluster multiplicity')
    return available,rows,groups


def _trigger(path,transport,source,watched,acquisition_run,forward,response):
    path,meta,proof,summary=_producer(path,transport,watched,'trigger')
    _require(_watch(proof['input_path'], proof.get('input_sha256'), watched) == response, 'Trigger and central use different response products')
    _require(summary==proof.get('summary') and summary.get('status')=='trigger_diagnostic_complete', 'Trigger summary mismatch')
    _require(meta == {k:v for k,v in proof.items() if k not in ('config_sha256','result_sha256')}, 'Trigger metadata/provenance mismatch')
    _require(_integer(summary,'events')==len(source['run']), 'Trigger event count mismatch')
    config=_watch(path.with_name('config.root'),proof.get('config_sha256'),watched)
    with uproot.open(config) as f:
        cfg=_strict_json(f,'metadata')
    _require(_integer(cfg,'historical_run',2**31-1)==acquisition_run and _integer(proof,'historical_run',2**31-1)==acquisition_run, 'Trigger acquisition run mismatch')
    _require(cfg.get('mode')==proof.get('mode')==meta.get('mode'), 'Trigger mode mismatch')
    if proof.get('forward_path') is not None:
        _require(Path(proof['forward_path']).resolve(strict=True)==Path(forward).resolve(strict=True)
                 and proof.get('forward_sha256')==watched[Path(forward).resolve(strict=True)], 'Trigger uses different measured forward product')
    with uproot.open(path) as f:
        fields=dict(KEYS,source_entry='int64',**{k:'int32' for k in ('accepted','bgo','three_particle','itrig','known_bits','bit_values','historical_run')})
        rows=_table(f,'trigger_events',fields)
    _ledger(rows,source)
    _require(np.all(rows['historical_run']==acquisition_run),'Trigger ledger acquisition run mismatch')
    mode=proof['mode']
    _require(mode in ('none','bgo','three_particle','either'),'Unknown trigger mode')
    for i in range(len(source['run'])):
        for key in ('accepted','bgo','three_particle'):
            _require(int(rows[key][i]) in (-1,0,1),'Invalid trigger ternary decision')
        bgo,three=(None if rows[k][i]==-1 else bool(rows[k][i]) for k in ('bgo','three_particle'))
        known=(1 if bgo is not None else 0)|(8 if three is not None else 0)
        bits=(1 if bgo else 0)|(8 if three else 0)
        enabled={'none':[],'bgo':[bgo],'three_particle':[three],'either':[bgo,three]}[mode]
        accepted=1 if not enabled or any(v is True for v in enabled) else -1 if any(v is None for v in enabled) else 0
        _require((int(rows['known_bits'][i]),int(rows['bit_values'][i]),int(rows['itrig'][i]),int(rows['accepted'][i])) ==
                 (known,bits,bits if known==9 else -1,accepted),'Incoherent trigger decision/bits')
    for key,value in [('accepted',1),('rejected',0),('unavailable',-1)]:
        _require(_integer(summary,key)==int(np.count_nonzero(rows['accepted']==value)),'Trigger summary decision mismatch')
    return rows


def _write_h70(path, eligible, central, forward, tagger, acquisition_run, polarization):
    import ROOT
    ROOT.gROOT.SetBatch(True)
    f=ROOT.TFile.Open(str(path),'CREATE')
    _require(bool(f) and not f.IsZombie(),'Cannot create h70 ROOT file')
    tree=ROOT.TTree('h70','Measured detector inputs; diagnostic only')
    scalars={'Idrun':('I','i',acquisition_run),'Ipol':('B','b',polarization),
             'Ncstrip':('i','I',0),'Nass_3':('i','I',0),'Nparf':('i','I',0),
             'N_traf':('i','I',0),'Nparf_strange':('B','b',0)}
    buffers={}
    for name,(code,leaf,initial) in scalars.items():
        buffers[name]=array(code,[initial]); tree.Branch(name,buffers[name],f'{name}/{leaf}')
    arrays={'Xstrip':('f','F','Ncstrip',128),'Eg_tag_strip':('f','F','Ncstrip',128),
            'Itipo_track':('i','I','Nass_3',291),'Index_trf':('B','b','Nparf',90),
            'Iass_trf':('B','b','N_traf',90)}
    arrays.update({k:('f','F','Nass_3',291) for k in ('Eclusc_track','Dedx_track','Thet_centr_track','Phi_centr_track')})
    arrays.update({k:('f','F','Nparf',90) for k in ('Theta_trf','Phi_trf','Tof_trf','De_trf')})
    for name,(code,leaf,count,capacity) in arrays.items():
        buffers[name]=array(code,[0]*capacity); tree.Branch(name,buffers[name],f'{name}[{count}]/{leaf}')
    _,c,cg=central[:3]; _,p,pg,m,mg,strange=forward[:6]; _,t,tg=tagger
    mapping=[(c,cg,dict(Itipo_track='type',Eclusc_track='bgo_energy_GeV',Dedx_track='dedx_MeV',Thet_centr_track='theta_deg',Phi_centr_track='phi_deg')),
             (p,pg,dict(Index_trf='source_match_index',Theta_trf='theta_deg',Phi_trf='phi_deg',Tof_trf='tof_ns',De_trf='de_MeV')),
             (m,mg,dict(Iass_trf='mask')),(t,tg,dict(Xstrip='xstrip',Eg_tag_strip='energy_GeV'))]
    try:
        for i in np.flatnonzero(eligible):
            for name,value in [('Ncstrip',len(tg[i])),('Nass_3',len(cg[i])),('Nparf',len(pg[i])),('N_traf',len(mg[i])),('Nparf_strange',int(strange[i]))]:
                buffers[name][0]=value
            for rows,groups,fields in mapping:
                for target,source in fields.items():
                    for j,row in enumerate(groups[i]):
                        buffers[target][j]=rows[source][row].item()
            _require(tree.Fill() >= 0, 'Failed to fill h70 event')
        _require(tree.Write() > 0, 'Failed to write h70 tree')
        _require(ROOT.TObjString(json.dumps(dict(mode=MODE,physical_validation=False,physics_validation=False))).Write('metadata') > 0, 'Failed to write h70 metadata')
    finally:
        f.Close()


def export_h70(input_root, central_root, forward_root, trigger_root, output, *, period,
               acquisition_run, polarization, tagger_root=None, generation_ledger_root=None):
    """Publish minimal native h70 and every transport event, without truth fallback.

    Missing tagger means unavailable, distinct from an available zero-cluster
    measurement. Only known accepted trigger decisions with all detector domains
    available produce h70 entries. A known partial OR decision may be accepted.
    Returns ``output/raw/<period>/run<acquisition_run>.root``.
    """
    acquisition=validate_acquisition(period,acquisition_run,polarization)
    output=Path(os.path.abspath(output))
    if output.exists() or output.is_symlink():
        raise FileExistsError(f'Refusing to overwrite h70 output: {output}')
    transport=Path(input_root).resolve(strict=True)
    watched={transport:sha256(transport),REPO/'config/support/run_manifest.csv':sha256(REPO/'config/support/run_manifest.csv')}
    code_paths=[Path(__file__).resolve(), Path(__file__).with_name('central.py'), Path(__file__).with_name('trigger.py'), Path(__file__).with_name('root_output.py'), REPO/'00_common/io/filesystem.py']
    code_hashes={str(p.resolve()):sha256(p) for p in code_paths}
    watched.update({Path(p):digest for p,digest in code_hashes.items()})
    with uproot.open(transport) as f:
        summary=read_transport_summary(f)
        _require(summary.get('status')=='diagnostic_transport_only'
                 and _integer(summary,'aborted')==0,'Incomplete transport')
        source=_table(f,'events',dict(KEYS,aborted='int32',steps='uint64',hit_steps='uint64',total_edep_MeV='float64',bgo_edep_MeV='float64'))
    _require('period' not in summary or summary['period'] == period, 'Transport acquisition period mismatch')
    keys=_keys(source); size=len(keys)
    _require(keys==sorted(set(keys)) and all(run>=0 and event>=0 for run,event in keys),'Invalid/duplicate/reordered transport ledger')
    _require(_integer(summary,'events')==_integer(summary,'attempted_events')==size and np.all(source['aborted']==0),'Transport event conservation mismatch')
    _require(np.all(source['hit_steps']<=source['steps']),'Transport hit/callback mismatch')
    for name in ('total_edep_MeV','bgo_edep_MeV'):
        _range(source[name],0,np.finfo(np.float64).max,name)
    _require(np.all(source['bgo_edep_MeV']<=source['total_edep_MeV']+1e-9),'Transport BGO/total energy mismatch')
    for name,values in [('all_callbacks',source['steps']),('detector_steps',source['hit_steps']),('passive_callbacks',source['steps']-source['hit_steps'])]:
        _require(_integer(summary,name)==sum(map(int,values)),'Transport summary count mismatch')
    central=_central(central_root,transport,source,watched,period,acquisition_run)
    forward=_forward(forward_root,transport,source,watched,acquisition_run)
    tagger=_tagger(tagger_root,transport,source,watched,acquisition_run)
    trigger=_trigger(trigger_root,transport,source,watched,acquisition_run,forward_root,central[4])
    generation, weight_provenance = None, None
    if generation_ledger_root is not None:
        from mc_simulation.geant4.beam_ledger import read_beam_ledger
        generation, weight_provenance, weight_inputs = read_beam_ledger(
            generation_ledger_root, transport_root=transport)
        _ledger(generation,source)
        watched.update(weight_inputs)
        ledger_path=Path(generation_ledger_root).resolve(strict=True)
        if tagger_root is not None:
            with uproot.open(tagger_root) as f:
                tagger_meta=_strict_json(f,'metadata')
            with uproot.open(Path(tagger_root).with_name('provenance.root')) as f:
                tagger_proof=_strict_json(f,'metadata')
            _require(tagger_meta.get('beam_metadata') == weight_provenance
                     and tagger_proof.get('beam_metadata') == weight_provenance
                     and tagger_proof.get('input_sha256',{}).get(str(ledger_path)) == watched[ledger_path],
                     'Generation ledger must be the exact beam ledger used by tagger')
        for name in ('beam_ledger.py','export_truth.py','tagger.py'):
            beam_code=Path(__file__).with_name(name).resolve()
            code_hashes[str(beam_code)]=sha256(beam_code)
            watched[beam_code]=code_hashes[str(beam_code)]
    reason=np.zeros(size,dtype='uint32')
    for unavailable,bit in [(~central[0],1),(~forward[0],2),(~tagger[0],4),(trigger['accepted']==-1,8),(trigger['accepted']==0,16)]:
        reason[unavailable]|=bit
    eligible=reason==0
    entry=np.full(size,-1,dtype='int64'); entry[eligible]=np.arange(int(eligible.sum()),dtype='int64')
    config=dict(schema=1,mode=MODE,period=period,acquisition_run=acquisition_run,polarization=polarization,
                acquisition_mapping=acquisition,reason_bits=REASONS,physical_validation=False,physics_validation=False,
                weight_policy='unavailable: no immutable generation weight supplied',efficiency_validation=False,
                tagger_policy='measured product only; absent input unavailable; Xstrip is mean strip index',
                producer_policy='mixed diagnostic response profiles; no historical acquisition equivalence',
                selection_policy='known trigger acceptance and all measured domains available; PID delegated unchanged to PreAnalysis.C')
    weight_summary = dict(weight_available_events=0, sumw=None, sumw2=None)
    if generation is not None:
        weight_summary=dict(weight_available_events=size,
                            sumw=float(np.sum(generation['generation_weight'])),
                            sumw2=float(np.sum(generation['generation_weight']**2)),
                            source_events=weight_provenance['source_events'], exported_events=size)
        config.update(weight_policy=weight_provenance['weight_policy'],
                      generation_ledger_path=str(ledger_path), generation_ledger_sha256=watched[ledger_path],
                      generation_provenance=weight_provenance, weight_summary=weight_summary)
    with atomic_output_directory(output, overwrite=False) as staging:
        raw=staging/'raw'/period; raw.mkdir(parents=True)
        result=raw/f'run{acquisition_run}.root'
        _write_h70(result,eligible,central,forward,tagger,acquisition_run,polarization)
        values=dict(run=source['run'],event=source['event'],source_entry=np.arange(size,dtype='uint64'),
                    central_available=central[0].astype('int32'),forward_available=forward[0].astype('int32'),
                    tagger_available=tagger[0].astype('int32'),trigger_accepted=trigger['accepted'],
                    central_association_status=central[3]['association_status'],central_bgo_status=central[3]['bgo_status'],
                    central_ca_source_nero=central[3]['ca_source_nero'],
                    forward_association_status=forward[6]['association_status'],
                    forward_wall_multiplicity_rejected=forward[7]['wall_multiplicity_rejected'],
                    trigger_itrig=trigger['itrig'],reason_bits=reason,h70_entry=entry,
                    weight_available=np.full(size,int(generation is not None),dtype='int32'),
                    generation_weight=(generation['generation_weight'] if generation is not None
                                       else np.full(size,np.nan,dtype='float64')))
        with uproot.create(staging/'ledger.root') as f:
            tree=f.mktree('h70_events',{key:str(value.dtype) for key,value in values.items()})
            if size: tree.extend(values)
            f['metadata']=json.dumps(config,sort_keys=True,allow_nan=False)
            f['summary']=json.dumps(dict(events=size,h70_entries=int(eligible.sum()),unavailable_or_rejected=int((~eligible).sum()),**weight_summary))
        _write_provenance(staging/'configuration.root',config)
        proof=dict(schema=1,mode=MODE,input_sha256={str(p):d for p,d in watched.items()},
                   code_sha256=code_hashes,configuration=config,
                   output_sha256={str(p.relative_to(staging)):sha256(p) for p in (result,staging/'ledger.root',staging/'configuration.root')},
                   events=size,h70_entries=int(eligible.sum()),weight_summary=weight_summary,
                   physical_validation=False,physics_validation=False,efficiency_validation=False)
        _write_provenance(staging/'provenance.root',proof)
        for path,digest in watched.items():
            _require(sha256(path)==digest,f'Immutable input changed before h70 publication: {path}')
    return output/'raw'/period/f'run{acquisition_run}.root'
