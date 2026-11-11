"""Synthetic measured-product fixtures; no transport truth substitutes measurements."""
from pathlib import Path
import pytest

from mc_simulation.geant4.h70 import validate_acquisition


def test_acquisition_is_explicit_repository_mapping():
    assert validate_acquisition('1998_uv', 1321, 1)['source_period'] == '1998_uv'
    for period, run, pol in [('2002_d1', 1321, 1), ('../1998_uv', 1321, 1),
                             ('1998_uv', True, 1), ('1998_uv', 1321, 255)]:
        with pytest.raises(ValueError):
            validate_acquisition(period, run, pol)

import json
import numpy as np
import uproot
from mc_simulation.geant4.central import sha256


def write_product(path, tables, metadata):
    """Write native scalar TTrees from (schema, rows); metadata are TObjStrings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with uproot.recreate(path) as f:
        for name, (schema, rows) in tables.items():
            t = f.mktree(name, schema)
            if rows:
                t.extend({k: np.asarray([r[k] for r in rows], dtype=dt) if dt != 'string'
                          else [r[k] for r in rows] for k,dt in schema.items()})
        for name, value in metadata.items():
            f[name] = json.dumps(value)


def build_measured_inputs(tmp_path, *, events=None, tagger=True, acquisition_run=1321, period='1998_uv', transport_root=None):
    """Return export_h70 kwargs for synthetic measured native products.

    events entries accept central, matches, forward, tags lists, central_available,
    partial_shape, accepted, tagger_available, wall_rejected. Each object uses
    bridge/native field names; tag strip alias is accepted. No truth is read.
    """
    events = events if events is not None else [dict(central=[dict(type=11,bgo_energy_GeV=.2,dedx_MeV=0.,theta_deg=60.,phi_deg=20.)],
        matches=[dict(mask=2)],forward=[dict(source_match_index=1,theta_deg=10.,phi_deg=30.,tof_ns=12.,de_MeV=5.)],tags=[dict(energy_GeV=1.2,strip=1.)])]
    base=Path(tmp_path); base.mkdir(parents=True,exist_ok=True)
    transport=Path(transport_root) if transport_root is not None else base/'transport.root'
    keys=dict(run='int32',event='int32'); ekeys=dict(keys,source_entry='uint64')
    identity=lambda i:dict(run=0,event=i)
    src=[dict(identity(i),aborted=0,steps=0,hit_steps=0,total_edep_MeV=0.,bgo_edep_MeV=0.) for i in range(len(events))]
    summary=dict(status='diagnostic_transport_only',period=period,output_format='ROOT_TTree',hit_schema_version=2,aborted=0,events=len(events),attempted_events=len(events),all_callbacks=0,detector_steps=0,passive_callbacks=0)
    if transport_root is None:
        write_product(transport,{'events':(dict(keys,aborted='int32',steps='uint64',hit_steps='uint64',total_edep_MeV='float64',bgo_edep_MeV='float64'),src)},dict(summary=summary))
    response=base/'response.root'
    response_meta=dict(historical_run=acquisition_run,period=period,input_path=str(transport.resolve()))
    response_launcher=dict(input_path=str(transport.resolve()),input_sha256=sha256(transport))
    write_product(response,{},dict(metadata=response_meta,launcher_provenance=response_launcher))
    code={str(Path(__file__).resolve()):sha256(__file__)}
    paths={}
    for kind in ('central','forward','tagger','trigger'):
        if kind=='tagger' and not tagger: continue
        folder=base/kind; folder.mkdir()
        path=folder/(kind+'.root'); paths[kind+'_root']=path
        config=folder/('config.root' if kind in ('trigger','tagger') else 'configuration.root')
        mode=f'selected26_{kind}_reconstruction_diagnostic'
        cfg=dict(mode=mode, schema=1)
        if kind=='forward': cfg['reconstruction']=dict(source_run=acquisition_run)
        if kind=='trigger': cfg=dict(mode='either',threshold_GeV=.1,historical_run=acquisition_run)
        write_product(config,{},dict(metadata=cfg))
        proof=dict(mode=mode,physical_validation=False,physics_validation=False,code_sha256=code,
                   transport_path=str(transport.resolve()),transport_sha256=sha256(transport),configuration=cfg)
        rows=[]; tables={}; sm=dict(events=len(events),physical_validation=False,physics_validation=False)
        if kind=='central':
            schema=dict(ekeys,status='string',**{k:'int32' for k in 'association_available association_status bgo_status bgo_measurements_available barrel_input_available cylinder_input_available barrel_status associations good_bgo sp_bgo barrel_records cylinder_tracks ca_source_nero'.split()})
            ass=[]
            for i,e in enumerate(events):
                central=e.get('central',[]); available=e.get('central_available',True)
                rows.append(dict(identity(i),source_entry=i,status=('diagnostic_objects' if central else 'diagnostic_no_object') if available else 'unsupported_central',association_available=int(available),association_status=0 if available else -1,bgo_status=16 if e.get('partial_shape') else 0,bgo_measurements_available=1,barrel_input_available=1,cylinder_input_available=int(available),barrel_status=0,associations=len(central),good_bgo=len(central),sp_bgo=0,barrel_records=len(central),cylinder_tracks=min(5,len(central)),ca_source_nero=0))
                for j,a in enumerate(central):
                    ass.append(dict(dict(identity(i),association_index=j,bgo=j+1,barrel=j+1 if a['type'] in (13,14) else 0,cylinder=0),**a))
            tables['central_events']=(schema,rows)
            tables['central_associations']=(dict(keys,**{k:'int32' for k in ('association_index','bgo','barrel','cylinder','type')},**{k:'float64' for k in ('bgo_energy_GeV','dedx_MeV','theta_deg','phi_deg')}),ass)
            sm.update(status='selected26_central_diagnostic_complete',associations=len(ass),unsupported_events=sum(not e.get('central_available',True) for e in events))
            proof.update(response_path=str(response.resolve()),configuration_path=str(config.resolve()),input_sha256={str(transport.resolve()):sha256(transport),str(config.resolve()):sha256(config),str(response.resolve()):sha256(response)})
            meta=dict(proof,config_path=str(config.resolve()))
            objects=dict(metadata=meta,config_metadata=cfg,summary=sm,response_metadata=response_meta,response_launcher_provenance=response_launcher)
        elif kind=='forward':
            schema=dict(ekeys,status='string',**{k:'int32' for k in 'planar_available wall_response_available shower_response_available wall_response_status shower_response_status wall_reconstruction_status shower_reconstruction_status association_status'.split()},**{k:'uint64' for k in ('particles','matches','wall_clusters','shower_clusters','planar_tracks')})
            particles=[]; matches=[]; counts=[]
            for i,e in enumerate(events):
                pp=e.get('forward',[]); mm=e.get('matches',[])
                rows.append(dict(identity(i),source_entry=i,status='diagnostic_wall_rejected' if e.get('wall_rejected') else 'diagnostic_particles' if pp else 'diagnostic_no_particle',planar_available=1,wall_response_available=1,shower_response_available=1,wall_response_status=0,shower_response_status=0,wall_reconstruction_status=0,shower_reconstruction_status=0,association_status=0,particles=len(pp),matches=len(mm),wall_clusters=len(mm),shower_clusters=len(mm),planar_tracks=len(mm)))
                counts.append(dict(identity(i),strange=e.get('strange',0),wall_multiplicity_rejected=int(e.get('wall_rejected',False))))
                for j,m in enumerate(mm):
                    mask=m['mask']; matches.append(dict(identity(i),match_index=j,planar=j+1 if mask&4 else 0,wall=j+1 if mask&2 else 0,shower=j+1 if mask&1 else 0,**m))
                for j,p in enumerate(pp): particles.append(dict(identity(i),particle_index=j,**p))
            tables['forward_events']=(schema,rows)
            tables['forward_particles']=(dict(keys,particle_index='uint64',source_match_index='int32',**{k:'float64' for k in ('theta_deg','phi_deg','tof_ns','de_MeV')}),particles)
            tables['forward_matches']=(dict(keys,match_index='uint64',**{k:'int32' for k in ('mask','planar','wall','shower')}),matches)
            tables['forward_source_counts']=(dict(keys,strange='int32',wall_multiplicity_rejected='int32'),counts)
            sm.update(status='selected26_forward_diagnostic_complete',particles=len(particles),unsupported_events=0)
            proof.update(source_run=acquisition_run,input_path=str(transport.resolve()),input_sha256=sha256(transport),tracking_path=str(transport.resolve()),tracking_sha256=sha256(transport),config_path=str(config.resolve()),config_sha256=sha256(config),executable_sha256='0'*64)
            objects=dict(metadata=proof.copy(),config_metadata=cfg,summary=sm,launcher_provenance=proof.copy())
        elif kind=='tagger':
            clusters=[]
            for i,e in enumerate(events):
                tags=e.get('tags',[]); available=e.get('tagger_available',True)
                rows.append(dict(identity(i),source_entry=i,available=int(available),nclusters=len(tags),status=0 if tags else 1 if available else 2))
                for j,t in enumerate(tags): clusters.append(dict(identity(i),cluster_index=j,xstrip=t.get('xstrip',t.get('strip')),energy_GeV=t['energy_GeV'],multiplicity=1))
            tables['tagger_events']=(dict(ekeys,available='int32',nclusters='int32',status='int32'),rows)
            tables['tagger_clusters']=(dict(keys,cluster_index='int32',xstrip='float64',energy_GeV='float64',multiplicity='int32'),clusters)
            proof.update(mode='legacy09_simulated_tagger_diagnostic',acquisition_run=acquisition_run,input_sha256={str(transport.resolve()):sha256(transport),str(config.resolve()):sha256(config)})
            sm=dict(status='legacy09_simulated_tagger_diagnostic_complete',events=len(events),available_events=sum(r['available'] for r in rows),clusters=len(clusters),physics_validation=False)
            objects=dict(metadata=proof.copy(),summary=sm)
            proof['summary']=sm
        else:
            for i,e in enumerate(events):
                accepted=e.get('accepted',1)
                rows.append(dict(identity(i),source_entry=i,accepted=accepted,bgo=1 if accepted==1 else 0 if accepted==0 else -1,three_particle=0 if accepted==0 else -1,itrig=0 if accepted==0 else -1,known_bits=9 if accepted==0 else 1 if accepted==1 else 0,bit_values=1 if accepted==1 else 0,historical_run=acquisition_run))
            tables['trigger_events']=(dict(keys,source_entry='int64',**{k:'int32' for k in ('accepted','bgo','three_particle','itrig','known_bits','bit_values','historical_run')}),rows)
            sm.update(status='trigger_diagnostic_complete',accepted=sum(r['accepted']==1 for r in rows),rejected=sum(r['accepted']==0 for r in rows),unavailable=sum(r['accepted']==-1 for r in rows))
            proof.update(mode='either',historical_run=acquisition_run,summary=sm,config_sha256=sha256(config),input_path=str(response.resolve()),input_sha256=sha256(response))
            objects=dict(metadata={k:v for k,v in proof.items() if k!='config_sha256'},summary=sm)
        write_product(path,tables,objects)
        if kind in ('central','forward'): proof['summary']=sm
        proof['response_sha256' if kind=='forward' else 'result_sha256']=sha256(path)
        write_product(folder/'provenance.root',{},dict(metadata=proof))
    return dict(input_root=transport,**paths,period=period,acquisition_run=acquisition_run,polarization=1)

from mc_simulation.geant4.h70 import export_h70


def test_measured_bridge_preserves_native_schema_and_partial_acceptance(tmp_path):
    kwargs=build_measured_inputs(tmp_path/'inputs')
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result) as f:
        tree=f['h70']; assert tree.num_entries==1
        assert tree['Xstrip'].array(library='np')[0].tolist()==[1.]
        assert tree['Idrun'].array(library='np').dtype==np.dtype('uint32')
        assert tree['Index_trf'].array(library='np')[0].tolist()==[1]
        assert tree['Eclusc_track'].array(library='np')[0][0]==pytest.approx(.2)
        assert tree['Eg_tag_strip'].member('fLeaves')[0].member('fLeafCount').member('fName')=='Ncstrip'
    with uproot.open(result.parents[2]/'ledger.root') as f:
        a=f['h70_events'].arrays(library='np')
        assert a['h70_entry'].tolist()==[0]
        assert a['trigger_itrig'].tolist()==[-1]
        assert a['weight_available'].tolist()==[0]
        assert np.isnan(a['generation_weight']).all()
    with pytest.raises(FileExistsError): export_h70(**kwargs,output=tmp_path/'published')


@pytest.mark.parametrize('compact', [False, True])
def test_nohit_empty_vs_missing_tagger_and_all_event_conservation(tmp_path, compact):
    events=[dict(tags=[],partial_shape=True),dict(tagger_available=False),
            dict(tags=[],accepted=0),dict(tags=[],accepted=-1),dict(tags=[],central_available=False)]
    kwargs=build_measured_inputs(tmp_path/'inputs',events=events)
    if compact:
        from tests.test_geant4_compact_summary import mark_compact
        mark_compact(kwargs['input_root'])
        kwargs=build_measured_inputs(tmp_path/'compact_inputs', events=events,
                                     transport_root=kwargs['input_root'])
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result) as f: assert f['h70'].num_entries==1
    with uproot.open(result.parents[2]/'ledger.root') as f:
        a=f['h70_events'].arrays(library='np')
        assert a['reason_bits'].tolist()==[0,4,16,8,1]
        assert a['h70_entry'].tolist()==[0,-1,-1,-1,-1]
    kwargs['tagger_root']=None
    result=export_h70(**kwargs,output=tmp_path/'no_tagger')
    with uproot.open(result) as f: assert f['h70'].num_entries==0


def test_compact_storage_metadata_required_before_h70_publication(tmp_path):
    from tests.test_geant4_compact_summary import mark_compact
    kwargs = build_measured_inputs(tmp_path/'inputs')
    mark_compact(kwargs['input_root'], metadata_changes={'source_index': 'stored_row'})
    with pytest.raises(ValueError, match='compact storage metadata'):
        export_h70(**kwargs, output=tmp_path/'published')
    assert not (tmp_path/'published').exists()


def rewrite_table(path, table, mutate, *, resign=True):
    """Rebuild fixture without duplicate ROOT cycles; optionally rebind producer hash."""
    tables={}; metadata={}
    with uproot.open(path) as f:
        for name in f.keys(cycle=False):
            obj=f[name]
            if obj.classname=='TTree':
                values=obj.arrays(library='np'); schema={k:('string' if v.dtype==object else str(v.dtype)) for k,v in values.items()}
                rows=[{k:v[i].item() if isinstance(v[i],np.generic) else v[i] for k,v in values.items()} for i in range(obj.num_entries)]
                if name==table: mutate(schema,rows)
                tables[name]=(schema,rows)
            else: metadata[name]=json.loads(str(obj))
    write_product(path,tables,metadata)
    if resign:
        proofpath=Path(path).with_name('provenance.root')
        with uproot.open(proofpath) as f: proof=json.loads(str(f['metadata']))
        proof['response_sha256' if Path(path).stem=='forward' else 'result_sha256']=sha256(path)
        write_product(proofpath,{},dict(metadata=proof))


@pytest.mark.parametrize('product,table,mutator,match',[
    ('central_root','central_associations',lambda s,r:r[0].update(theta_deg=float('nan')),'finite/range'),
    ('central_root','central_associations',lambda s,r:r[0].update(bgo=99),'source reference'),
    ('central_root','central_events',lambda s,r:r[0].update(source_entry=1),'source_entry'),
    ('central_root','central_events',lambda s,r:s.update(associations='uint32'),'native branch type'),
    ('forward_root','forward_particles',lambda s,r:r[0].update(source_match_index=0),'one-based'),
    ('forward_root','forward_matches',lambda s,r:r[0].update(mask=4),'mask/reference'),
    ('tagger_root','tagger_clusters',lambda s,r:r[0].update(xstrip=129.),'strip index'),
    ('tagger_root','tagger_events',lambda s,r:r[0].update(available=0),'availability'),
    ('trigger_root','trigger_events',lambda s,r:r[0].update(itrig=1),'decision/bits'),
])
def test_malformed_measured_product_never_publishes(tmp_path,product,table,mutator,match):
    kwargs=build_measured_inputs(tmp_path/'inputs')
    rewrite_table(kwargs[product],table,mutator)
    with pytest.raises(ValueError,match=match): export_h70(**kwargs,output=tmp_path/'published')
    assert not (tmp_path/'published').exists()


def test_changed_result_fails_before_publication(tmp_path):
    kwargs=build_measured_inputs(tmp_path/'inputs')
    rewrite_table(kwargs['central_root'],'central_events',lambda s,r:None,resign=False)
    with pytest.raises(ValueError,match='SHA256'): export_h70(**kwargs,output=tmp_path/'published')
    assert not (tmp_path/'published').exists()


def test_strip_number_endpoints_and_partial_shape_supported(tmp_path):
    kwargs=build_measured_inputs(tmp_path/'inputs',events=[dict(partial_shape=True,tags=[dict(strip=1.,energy_GeV=1.2),dict(strip=128.,energy_GeV=.7)])])
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result) as f:
        assert f['h70']['Xstrip'].array(library='np')[0].tolist()==[1.,128.]
    rewrite_table(kwargs['tagger_root'],'tagger_clusters',lambda s,r:r[0].update(xstrip=0.))
    with pytest.raises(ValueError,match='strip index'): export_h70(**kwargs,output=tmp_path/'zero_strip')


def test_defined_negative_central_sentinel_and_wall_rejection_retained(tmp_path):
    kwargs=build_measured_inputs(tmp_path/'inputs',events=[dict(central=[dict(type=2,bgo_energy_GeV=-1.,dedx_MeV=-1.,theta_deg=-1.,phi_deg=0.)],wall_rejected=True)])
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result) as f:
        assert f['h70'].num_entries==1
        assert f['h70']['Eclusc_track'].array(library='np')[0].tolist()==[-1.]
    with uproot.open(result.parents[2]/'ledger.root') as f:
        assert f['h70_events']['forward_wall_multiplicity_rejected'].array(library='np').tolist()==[1]


def test_publication_failure_cleans_reserved_directory(tmp_path,monkeypatch):
    from mc_simulation.geant4 import h70
    kwargs=build_measured_inputs(tmp_path/'inputs')
    def fail(*args): raise RuntimeError('simulated ROOT write failure')
    monkeypatch.setattr(h70,'_write_h70',fail)
    with pytest.raises(RuntimeError,match='write failure'): export_h70(**kwargs,output=tmp_path/'published')
    assert not (tmp_path/'published').exists()
    assert not list(tmp_path.glob('.published.*'))


def test_real_tagger_producer_without_beam_feeds_h70(tmp_path):
    """Opt-in real recovered-histogram producer contract, not synthetic metadata."""
    import os
    from mc_simulation.geant4.tagger import reconstruct
    histogram=os.environ.get('GRAAL_TAGGER_HISTOGRAM_ROOT')
    if not histogram:
        pytest.skip('Set GRAAL_TAGGER_HISTOGRAM_ROOT to verified archived histogram extraction')
    kwargs=build_measured_inputs(tmp_path/'inputs',tagger=False,events=[{},{}])
    kwargs['tagger_root']=reconstruct(kwargs['input_root'],None,histogram,tmp_path/'tagger_producer',
                                     acquisition_run=1321,seed=7)
    with uproot.open(kwargs['tagger_root']) as f:
        assert 'events' not in json.loads(str(f['metadata']))
        assert json.loads(str(f['summary']))['events']==2
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result) as f: assert f['h70'].num_entries==0
    with uproot.open(result.parents[2]/'ledger.root') as f:
        assert f['h70_events']['reason_bits'].array(library='np').tolist()==[4,4]
        assert f['h70_events']['tagger_available'].array(library='np').tolist()==[0,0]


def test_tagger_summary_count_mismatch_is_rejected(tmp_path):
    kwargs=build_measured_inputs(tmp_path/'inputs')
    path=kwargs['tagger_root']
    with uproot.open(path) as f:
        tables={name:(dict((k,str(v.dtype)) for k,v in f[name].arrays(library='np').items()),
                     [dict((k,v[i].item()) for k,v in f[name].arrays(library='np').items()) for i in range(f[name].num_entries)])
                for name in ('tagger_events','tagger_clusters')}
        meta=json.loads(str(f['metadata'])); summary=json.loads(str(f['summary']))
    summary['events']=2
    write_product(path,tables,dict(metadata=meta,summary=summary))
    proofpath=path.with_name('provenance.root')
    with uproot.open(proofpath) as f: proof=json.loads(str(f['metadata']))
    proof.update(result_sha256=sha256(path),summary=summary)
    write_product(proofpath,{},dict(metadata=proof))
    with pytest.raises(ValueError,match='summary event count'): export_h70(**kwargs,output=tmp_path/'published')


@pytest.mark.parametrize('component,expected',[
    ('central_root','Central response acquisition run mismatch'),
    ('forward_root','Forward acquisition source_run mismatch'),
])
def test_crossjoin_same_transport_different_acquisition_run_rejected(tmp_path,component,expected):
    primary=build_measured_inputs(tmp_path/'primary')
    alternate=build_measured_inputs(tmp_path/'alternate',acquisition_run=1324,transport_root=primary['input_root'])
    # Both bundles are independently valid acquisition products of the same G4
    # transport. Rebinding result checksums alone cannot make this join valid.
    export_h70(**alternate,output=tmp_path/'valid_alternate')
    primary[component]=alternate[component]
    with pytest.raises(ValueError,match=expected): export_h70(**primary,output=tmp_path/'mixed')
    assert not (tmp_path/'mixed').exists()


def test_same_run_same_transport_different_response_products_rejected(tmp_path):
    primary=build_measured_inputs(tmp_path/'primary')
    alternate=build_measured_inputs(tmp_path/'alternate',transport_root=primary['input_root'])
    export_h70(**alternate,output=tmp_path/'valid_alternate')
    primary['trigger_root']=alternate['trigger_root']
    with pytest.raises(ValueError,match='different response products'):
        export_h70(**primary,output=tmp_path/'mixed')
    assert not (tmp_path/'mixed').exists()


def test_transport_period_conflict_rejected_before_products(tmp_path):
    kwargs=build_measured_inputs(tmp_path/'inputs')
    kwargs.update(period='2002_d1',acquisition_run=3987)
    with pytest.raises(ValueError,match='Transport acquisition period mismatch'):
        export_h70(**kwargs,output=tmp_path/'mixed')


def build_weighted_measured_inputs(base, *, same_tagger_ledger=True):
    from tests.test_geant4_beam_ledger import build_replay_inputs
    from mc_simulation.geant4.beam_ledger import bind_beam_ledger
    base=Path(base)
    transport,truth,_=build_replay_inputs(base/'replay',count=5,source_count=7)
    beam=bind_beam_ledger(transport,truth,base/'beam.root')
    events=[dict(tags=[]),dict(tagger_available=False),dict(tags=[],accepted=0),
            dict(tags=[],accepted=-1),dict(tags=[],central_available=False)]
    kwargs=build_measured_inputs(base/'measured',events=events,transport_root=transport)
    if same_tagger_ledger:
        from tests.test_geant4_beam_ledger import mutate_native
        with uproot.open(beam) as f: meta=json.loads(str(f['metadata']))
        mutate_native(kwargs['tagger_root'],meta_mutate=lambda m:m.update(beam_metadata=meta))
        proofpath=kwargs['tagger_root'].with_name('provenance.root')
        with uproot.open(proofpath) as f: proof=json.loads(str(f['metadata']))
        proof.update(beam_metadata=meta,result_sha256=sha256(kwargs['tagger_root']))
        proof['input_sha256'].update(meta['source_sha256'])
        proof['input_sha256'][str(beam.resolve())]=sha256(beam)
        write_product(proofpath,{},dict(metadata=proof))
    kwargs['generation_ledger_root']=beam
    return kwargs


def test_generation_weights_preserve_all_rejected_and_unavailable_denominator_rows(tmp_path):
    kwargs=build_weighted_measured_inputs(tmp_path/'inputs')
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result.parents[2]/'ledger.root') as f:
        rows=f['h70_events'].arrays(library='np')
        summary=json.loads(str(f['summary'])); meta=json.loads(str(f['metadata']))
        assert rows['reason_bits'].tolist()==[0,4,16,8,1]
        assert rows['weight_available'].tolist()==[1]*5
        assert rows['generation_weight'].tolist()==[1.]*5
        assert rows['h70_entry'].tolist()==[0,-1,-1,-1,-1]
        assert summary['sumw']==summary['sumw2']==5.
        assert summary['source_events']==7 and summary['exported_events']==5
        assert meta['efficiency_validation'] is False
        assert meta['generation_provenance']['source_identity']['polarization']=='not_modeled'
    with uproot.open(result.parents[2]/'provenance.root') as f:
        proof=json.loads(str(f['metadata']))
        assert str(kwargs['generation_ledger_root'].resolve()) in proof['input_sha256']


def test_generation_ledger_must_match_tagger_beam_input(tmp_path):
    kwargs=build_weighted_measured_inputs(tmp_path/'inputs',same_tagger_ledger=False)
    with pytest.raises(ValueError,match='exact beam ledger used by tagger'):
        export_h70(**kwargs,output=tmp_path/'published')
    assert not (tmp_path/'published').exists()


def test_generation_ledger_wrong_transport_rejected(tmp_path):
    kwargs=build_weighted_measured_inputs(tmp_path/'inputs')
    other=build_weighted_measured_inputs(tmp_path/'other')
    kwargs['generation_ledger_root']=other['generation_ledger_root']
    with pytest.raises(ValueError,match='transport identity'):
        export_h70(**kwargs,output=tmp_path/'published')
    assert not (tmp_path/'published').exists()


def test_generation_weights_available_even_when_tagger_product_absent(tmp_path):
    kwargs=build_weighted_measured_inputs(tmp_path/'inputs')
    kwargs['tagger_root']=None
    result=export_h70(**kwargs,output=tmp_path/'published')
    with uproot.open(result.parents[2]/'ledger.root') as f:
        rows=f['h70_events'].arrays(library='np')
        assert rows['weight_available'].tolist()==[1]*5
        assert rows['generation_weight'].tolist()==[1.]*5
        assert rows['h70_entry'].tolist()==[-1]*5


def test_identical_ledger_at_different_path_cannot_replace_tagger_input(tmp_path):
    import shutil
    kwargs=build_weighted_measured_inputs(tmp_path/'inputs')
    substitute=tmp_path/'different-beam.root'
    shutil.copyfile(kwargs['generation_ledger_root'],substitute)
    kwargs['generation_ledger_root']=substitute
    with pytest.raises(ValueError,match='exact beam ledger used by tagger'):
        export_h70(**kwargs,output=tmp_path/'published')
    assert not (tmp_path/'published').exists()
