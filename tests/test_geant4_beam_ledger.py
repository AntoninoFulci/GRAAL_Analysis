"""Native ROOT replay input binding and denominator conservation."""
from array import array
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import uproot

from mc_simulation.geant4.beam_ledger import bind_beam_ledger, read_beam_ledger, WEIGHT_POLICY
from mc_simulation.geant4.central import sha256
from mc_simulation.geant4.export_truth import M_PROTON
from tests.test_geant4_h70 import write_product


def build_replay_inputs(base, *, count=3, source_count=5):
    """Physically conserved minimal truth with real immutable generator ROOT metadata."""
    import ROOT
    base = Path(base); base.mkdir(parents=True, exist_ok=True)
    source = base/'generator.root'
    from graal_common.physics.channels import get_channel
    from mc_simulation.geant4.export_truth import export_truth
    photons=get_channel('eta_pi0').photon_branches
    with ROOT.TFile.Open(str(source), 'RECREATE') as root:
        tree=ROOT.TTree('mc','fixture generator ledger')
        vectors={name:ROOT.TLorentzVector() for name in ('beam_true','proton_true',*(p+'_true' for p in photons))}
        for name,value in vectors.items(): tree.Branch(name,value)
        for i in range(source_count):
            energy=1.2+.01*i
            vectors['beam_true'].SetPxPyPzE(0.,0.,energy,energy)
            vectors['proton_true'].SetPxPyPzE(0.,0.,0.,M_PROTON)
            for name in photons: vectors[name+'_true'].SetPxPyPzE(0.,0.,energy/len(photons),energy/len(photons))
            tree.Fill()
        tree.Write()
        for key,val in dict(generator='generate_eta_pi0_dataset',
                            sampling='accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace',
                            root_version=ROOT.gROOT.GetVersion()).items():
            ROOT.TNamed(key,val).Write()
        for key,val in dict(seed=7,n_generated=source_count,n_requested=source_count,
                            generator_schema_version=1,truth_schema_version=1).items():
            ROOT.TParameter('int')(key,val).Write()
        for key,val in dict(beam_min_gev=1.1,beam_max_gev=1.5).items():
            ROOT.TParameter('double')(key,val).Write()
    export_truth(source,base/'export',channel='eta_pi0',max_events=count)
    truth=base/'export/truth.root'
    with uproot.open(truth) as root: prim=root['primaries'].arrays(library='np')
    actual=[]
    for i in range(len(prim['event'])):
        actual.append(dict(run=0,event=int(prim['event'][i]),vertex=0,particle=int(prim['primary_index'][i]),
                           pdg=int(prim['pdg'][i]),vertex_weight=1.,particle_weight=1.,
                           px_MeV=float(prim['px_GeV'][i])*1000.,py_MeV=float(prim['py_GeV'][i])*1000.,
                           pz_MeV=float(prim['pz_GeV'][i])*1000.,
                           kinetic_MeV=float(prim['energy_GeV'][i]-prim['mass_GeV'][i])*1000.))
    transport=base/'transport.root'
    summary=dict(status='diagnostic_transport_only',source_mode='root_replay',output_format='ROOT_TTree',
                 hit_schema_version=2,events=count,attempted_events=count,aborted=0,
                 replay_input_path=str(truth.resolve()),replay_input_md5=hashlib.md5(truth.read_bytes()).hexdigest(),
                 all_callbacks=0,detector_steps=0,passive_callbacks=0,period='1998_uv')
    write_product(transport,dict(events=(dict(run='int32',event='int32',aborted='int32',steps='uint64',hit_steps='uint64',total_edep_MeV='float64',bgo_edep_MeV='float64'),
                 [dict(run=0,event=i,aborted=0,steps=0,hit_steps=0,total_edep_MeV=0.,bgo_edep_MeV=0.) for i in range(count)]),
                 primaries=(dict(run='int32',event='int32',vertex='int32',particle='int32',pdg='int32',**{k:'float64' for k in ('vertex_weight','particle_weight','px_MeV','py_MeV','pz_MeV','kinetic_MeV')}),actual)),dict(summary=summary))
    # Native transport path and digest objects contain plain text, not JSON strings.
    with uproot.update(transport) as root:
        root['input_source']=str(truth.resolve()); root['input_md5']=summary['replay_input_md5']
    return transport,truth,source


def mutate_native(path, table=None, mutate=None, meta_mutate=None):
    tables={}; objects={}
    with uproot.open(path) as root:
        for name in root.keys(cycle=False):
            obj=root[name]
            if obj.classname=='TTree':
                values=obj.arrays(library='np'); types={k:str(v.dtype) for k,v in values.items()}
                rows=[{k:v[i].item() for k,v in values.items()} for i in range(obj.num_entries)]
                if name==table: mutate(types,rows)
                tables[name]=(types,rows)
            else: objects[name]=str(obj)
    if meta_mutate:
        meta=json.loads(objects['metadata' if 'metadata' in objects else 'summary'])
        meta_mutate(meta); objects['metadata' if 'metadata' in objects else 'summary']=json.dumps(meta)
    write_product(path,tables,{})
    with uproot.update(path) as root:
        for name,text in objects.items(): root[name]=text


@pytest.mark.parametrize('compact', [False, True])
def test_binding_preserves_prefix_denominator_and_zero_hit_events(tmp_path, compact):
    transport,truth,source=build_replay_inputs(tmp_path/'input')
    if compact:
        from tests.test_geant4_compact_summary import mark_compact
        mark_compact(transport)
    result=bind_beam_ledger(transport,truth,tmp_path/'beam.root')
    values,meta,watched=read_beam_ledger(result,transport_root=transport)
    assert values['event'].tolist()==[0,1,2]
    assert values['generation_weight'].tolist()==[1.,1.,1.]
    assert meta['source_events']==5 and meta['exported_events']==3
    assert meta['sumw']==meta['sumw2']==3.
    assert source.resolve() in watched
    with pytest.raises(FileExistsError): bind_beam_ledger(transport,truth,result)


def test_compact_storage_metadata_required_before_beam_publication(tmp_path):
    from tests.test_geant4_compact_summary import mark_compact
    transport, truth, _ = build_replay_inputs(tmp_path/'input')
    mark_compact(transport, metadata=False)
    with pytest.raises(ValueError, match='storage_metadata'):
        bind_beam_ledger(transport, truth, tmp_path/'beam.root')
    assert not (tmp_path/'beam.root').exists()


@pytest.mark.parametrize('table,mutate,match',[
    ('events',lambda s,r:r.reverse(),'ordered'),
    ('events',lambda s,r:r.pop(),'ordered'),
    ('events',lambda s,r:s.update(event='uint32'),'scalar type'),
    ('events',lambda s,r:r[0].update(aborted=1),'Aborted'),
    ('primaries',lambda s,r:r[1].update(pz_MeV=1201.),'momentum'),
    ('primaries',lambda s,r:r[1].update(particle_weight=2.),'weights'),
    ('primaries',lambda s,r:r[1].update(kinetic_MeV=1201.),'kinetic'),
])
def test_invalid_transport_never_publishes(tmp_path,table,mutate,match):
    transport,truth,_=build_replay_inputs(tmp_path/'input')
    mutate_native(transport,table,mutate)
    with pytest.raises(ValueError,match=match): bind_beam_ledger(transport,truth,tmp_path/'beam.root')
    assert not (tmp_path/'beam.root').exists()


def test_same_count_different_truth_is_not_a_transport_binding(tmp_path):
    transport,_,_=build_replay_inputs(tmp_path/'one')
    _,other,_=build_replay_inputs(tmp_path/'two')
    with pytest.raises(ValueError,match='input identity'): bind_beam_ledger(transport,other,tmp_path/'beam.root')
    assert not (tmp_path/'beam.root').exists()


@pytest.mark.parametrize('mutation,match',[
    (lambda m:m.update(source_mode='gps'),'ROOT replay'),
    (lambda m:m.update(replay_input_md5='0'*32),'input identity'),
    (lambda m:m.update(events=2),'conservation'),
])
def test_native_input_proof_required(tmp_path,mutation,match):
    transport,truth,_=build_replay_inputs(tmp_path/'input')
    mutate_native(transport,meta_mutate=mutation)
    with pytest.raises(ValueError,match=match): bind_beam_ledger(transport,truth,tmp_path/'beam.root')


@pytest.mark.parametrize('field,value,match',[
    ('generation_weight',2.,'unit-unweighted'),('energy_GeV',1.25,'transported truth'),
    ('source_entry',2,'ordered')])
def test_modified_beam_mapping_or_weights_rejected(tmp_path,field,value,match):
    transport,truth,_=build_replay_inputs(tmp_path/'input')
    result=bind_beam_ledger(transport,truth,tmp_path/'beam.root')
    mutate_native(result,'beam_events',lambda s,r:r[0].update({field:value}))
    with pytest.raises(ValueError,match=match): read_beam_ledger(result,transport_root=transport)


def test_changed_original_source_rejected(tmp_path):
    transport,truth,source=build_replay_inputs(tmp_path/'input')
    result=bind_beam_ledger(transport,truth,tmp_path/'beam.root')
    with source.open('ab') as stream: stream.write(b'changed')
    with pytest.raises(ValueError,match='SHA256'): read_beam_ledger(result,transport_root=transport)


def test_changed_input_during_publication_leaves_no_output(tmp_path,monkeypatch):
    from mc_simulation.geant4 import beam_ledger
    transport,truth,_=build_replay_inputs(tmp_path/'input')
    def fail(_): raise ValueError('changed before publication')
    monkeypatch.setattr(beam_ledger,'_stable',fail)
    with pytest.raises(ValueError,match='changed before publication'):
        bind_beam_ledger(transport,truth,tmp_path/'beam.root')
    assert not (tmp_path/'beam.root').exists()
    assert not list(tmp_path.glob('.beam.root.*'))


def test_optional_launcher_manifest_is_hashed_and_requires_truth_identity(tmp_path):
    transport,truth,_=build_replay_inputs(tmp_path/'input')
    manifest=tmp_path/'run.json'
    manifest.write_text(json.dumps(dict(truth_root_sha256=sha256(truth))))
    result=bind_beam_ledger(transport,truth,tmp_path/'beam.root',run_manifest=manifest)
    _,meta,watched=read_beam_ledger(result,transport_root=transport)
    assert meta['run_manifest_path']==str(manifest.resolve()) and manifest.resolve() in watched
    manifest.write_text(json.dumps(dict(truth_root_sha256='0'*64)))
    with pytest.raises(ValueError,match='Launcher truth SHA256'):
        bind_beam_ledger(transport,truth,tmp_path/'invalid.root',run_manifest=manifest)
    assert not (tmp_path/'invalid.root').exists()
    with pytest.raises(ValueError,match='SHA256'):
        read_beam_ledger(result,transport_root=transport)
