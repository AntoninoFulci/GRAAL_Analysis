"""Measured central boundary fixtures, including the explicit modern PREAN profile."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import uproot
from tests.test_digitize import ROOT, SCHEMAS, put_tree, table
from mc_simulation.geant4 import central as launcher
from mc_simulation.geant4.bgo_config import write_bgo_config, write_modern_prean_profile
from mc_simulation.geant4.legacy_response import write_response_config, bgo_electronics
from mc_simulation.geant4.cylinder_config import write_cylinder_config

DATA=Path(__file__).resolve().parents[1]/"docs/reference/fortran/prog/data"
SETTINGS=dict(crystal_threshold=.001,cluster_threshold=.01,barrel_energy_threshold_mev=.5,
              ca_rcnt=.2,ca_tde=8,xba1=[0.]*32,
              initialization_claim="Synthetic composition fixture only; explicitly initialized values, no historical PREAN state assertion")


def metadata(path,name,value):
    root=ROOT.TFile(str(path),"UPDATE")
    try:
        root.cd();assert ROOT.TObjString(value if isinstance(value,str) else json.dumps(value)).Write(name,ROOT.TObject.kOverwrite)>0
    finally:root.Close()


def product(path,source,rows,kind):
    path.parent.mkdir();config=path.parent/"producer_config.root"
    producer_configuration=(write_response_config(DATA,1321,config) if kind=="response"
                            else write_cylinder_config(DATA,config))
    mode="legacy09_diagnostic" if kind=="response" else "selected26_old_cyl_diagnostic"
    summary=dict(schema_version=1,status="legacy09_diagnostic_complete" if kind=="response" else "selected26_old_cyl_diagnostic_complete",
                 events=len(rows["events"]),physics_validation=False)
    if kind=="cylinders":summary.update(tracks=len(rows["tracks"]),physical_validation=False)
    launch=dict(mode=mode,input_path=str(source),input_sha256=launcher.sha256(source),
                executable_sha256="0"*64,code_sha256={"synthetic_fixture":"1"*64},physics_validation=False)
    md=dict(schema_version=1,mode=mode,input_path=str(source),input_md5=hashlib.md5(source.read_bytes()).hexdigest(),
            config_path=str(config),physics_validation=False)
    if kind=="cylinders":md["physical_validation"]=False
    root=ROOT.TFile(str(path),"CREATE")
    common=dict(run="int32",event="int32",aborted="int32",total_edep_MeV="float64",bgo_edep_MeV="float64",steps="uint64",hit_steps="uint64",status="string")
    try:
        if kind=="response":
            put_tree(root,"response_events",dict(common,bgo_digits="int32",barrel_digits="int32"),rows["events"])
            put_tree(root,"bgo_digits",dict(run="int32",event="int32",channel="int32",adc="int32"),rows["bgo"])
            put_tree(root,"barrel_digits",dict(run="int32",event="int32",channel="int32",adc="int32",tdc="int32"),rows["barrel"])
        else:
            put_tree(root,"cylinder_events",dict(common,tracks="uint64",input_status="int32",response_status="int32",tracking_unsupported="int32",tracking_status="int32"),rows["events"])
            put_tree(root,"cylinder_tracks",dict(run="int32",event="int32",track_index="uint64",theta_deg="float64",phi_deg="float64"),rows["tracks"])
        root.cd()
        for name,value in dict(metadata=md,summary=summary,launcher_provenance=launch,config_metadata=producer_configuration).items():
            assert ROOT.TObjString(json.dumps(value)).Write(name)>0
    finally:root.Close()
    provenance=dict(launch,response_sha256=launcher.sha256(path),summary=summary,config_sha256=launcher.sha256(config))
    with uproot.create(path.parent/"provenance.root") as f:f["metadata"]=json.dumps(provenance)
    return path


def fixtures(tmp_path):
    source=tmp_path/"transport.root"
    events=[dict(run=7,event=i,aborted=0,total_edep_MeV=0.,bgo_edep_MeV=0.,steps=0,hit_steps=0) for i in range(5)]
    root=ROOT.TFile(str(source),"CREATE")
    try:
        for name,schema in SCHEMAS.items():put_tree(root,name,schema,events if name=="events" else [])
        root.cd();ROOT.TObjString(json.dumps(dict(status="diagnostic_transport_only",hit_schema_version=2,aborted=0,events=5,attempted_events=5,all_callbacks=0,passive_callbacks=0,detector_steps=0))).Write("summary")
    finally:root.Close()
    bgo=[dict(run=7,event=i,channel=225,adc=adc) for i,adc in [(0,200),(2,5),(3,200),(4,200)]]
    bgo.append(dict(run=7,event=4,channel=226,adc=150))
    barrel=[dict(run=7,event=i,channel=1,adc=400,tdc=500) for i in [0,3]]
    response_events=[dict(e,status="diagnostic_only",bgo_digits=sum(d["event"]==e["event"] for d in bgo),barrel_digits=sum(d["event"]==e["event"] for d in barrel)) for e in events]
    response=product(tmp_path/"response/response.root",source,dict(events=response_events,bgo=bgo,barrel=barrel),"response")
    tracks=[dict(run=7,event=0,track_index=0,theta_deg=90.,phi_deg=0.)]
    cyl_events=[dict(e,status="diagnostic_complete",tracks=int(e["event"]==0),input_status=0,response_status=0,tracking_unsupported=0,tracking_status=0) for e in events]
    cylinders=product(tmp_path/"cylinders/cylinders.root",source,dict(events=cyl_events,tracks=tracks),"cylinders")
    config=tmp_path/"config.root";write_bgo_config(DATA,config,**SETTINGS)
    return source,response,cylinders,config


@pytest.fixture
def native():
    path=os.environ.get("GRAAL_CENTRAL_EXE")
    if not path:pytest.skip("Set GRAAL_CENTRAL_EXE for native central ROOT composition")
    assert Path(path).is_file();return Path(path)


def run(native,paths,output):
    return subprocess.run([str(x) for x in (native,*paths,output,123)],capture_output=True,text=True,timeout=60)


def test_modern_profile_reaches_measured_chain_and_retains_provenance(native,tmp_path):
    source,response,cylinders,_=fixtures(tmp_path)
    evidence=tmp_path/"environment.txt"
    evidence.write_text("export BGO_SOFT_THRES=0.002\nexport CLUS_SOFT_THRES=0.015\n")
    config=tmp_path/"modern.root"
    profile=write_modern_prean_profile(DATA,config,environment_evidence=evidence)
    result=launcher.reconstruct(source,response,cylinders,config,tmp_path/"modern-output",native,123)
    with uproot.open(result) as root:
        assert json.loads(str(root["config_metadata"]))==profile
        assert json.loads(str(root["metadata"]))["limitations"]==(
            "explicit initialized reconstruction configuration; "
            "no historical runtime equivalence claimed; no truth/four-vectors/selection")
        events=root["central_events"].arrays(library="np")
        assert events["event"].tolist()==list(range(5))
        assert events["association_status"].tolist()==[0,0,0,8,0]
        assert events["uniform_draws"].tolist()==[1,0,1,1,2]
        barrel=root["central_barrel"].arrays(library="np")
        associations=root["central_associations"].arrays(library="np")
        # The selected26 nonzero attenuation actually enters the measured DEDX.
        assert associations["dedx_MeV"][associations["event"]==0][0]>2*barrel["energy_MeV"][barrel["event"]==0][0]
    with uproot.open(result.with_name("provenance.root")) as root:
        provenance=json.loads(str(root["metadata"]))
    assert provenance["configuration"]==profile
    assert provenance["configuration"]["modern_initialization"]["historical_runtime_reproduction"] is False
    assert provenance["configuration_source_sha256"][str(evidence.resolve())]==launcher.sha256(evidence)


def test_measured_ca_memberships_anabgo_anabar_association_and_nohit(native,tmp_path):
    paths=fixtures(tmp_path)
    for name in ("one","two"):
        p=run(native,paths,tmp_path/name);assert p.returncode==0,p.stderr
    path=tmp_path/"one/central.root";e=table(path,"central_events")
    assert e["event"].tolist()==list(range(5))
    assert e["ca_called"].tolist()==[1,0,1,1,1]
    assert e["accepted_bgo_digits"].tolist()==[1,0,1,1,2]
    assert e["uniform_draws"].tolist()==[1,0,1,1,2]
    assert e["association_status"].tolist()==[0,0,0,8,0]
    assert e["good_bgo"].tolist()==[1,0,0,1,1]
    assert e["sp_bgo"].tolist()==[0,0,1,0,0]
    assert e["bgo_status"][4]&16 and e["association_available"][4]==1
    associations=table(path,"central_associations")
    select=associations["event"]==0
    assert associations["type"][select].tolist()==[14]
    assert associations["bgo"][select].tolist()==[1]
    assert associations["barrel"][select].tolist()==[1]
    assert associations["cylinder"][select].tolist()==[1]
    assert associations["bgo_energy_GeV"][select][0]>.1
    assert associations["dedx_MeV"][select][0]>8
    assert associations["barrel_time_ns"][select][0]>20
    measured=table(path,"central_bgo_clusters")
    old=measured["event"]==4
    assert measured["old_shape_available"][old].tolist()==[0]
    assert np.isnan(measured["sx1"][old][0]) and np.isfinite(measured["corrected_energy_GeV"][old][0])
    members=table(path,"central_ca_members")
    assert members["crystal_id"].tolist()==[801,801,801,801,802]
    for event,index,ch in zip(members["event"],members["digit_index"],members["channel"]):
        grid=table(path,"central_bgo_grid");sel=(grid["event"]==event)&(grid["digit_index"]==index)
        assert grid["channel"][sel].tolist()==[ch]
    with uproot.open(path) as root:
        for name,kind in root.classnames(cycle=False).items():
            if kind=="TTree":
                a,b=table(path,name),table(tmp_path/"two/central.root",name)
                for key in a:
                    if np.issubdtype(a[key].dtype,np.floating):assert np.array_equal(a[key],b[key],equal_nan=True)
                    else:assert np.array_equal(a[key],b[key])


@pytest.mark.parametrize("case",["wrong_join","missing_event","digit_duplicate","digit_range","track_index","unavailable_track","config_type","config_index","json_type","root_cycle"])
def test_composition_boundary_rejects_malformed_measured_inputs(native,tmp_path,case):
    paths=fixtures(tmp_path);source,response,cylinders,config=paths
    if case=="wrong_join":
        with uproot.open(response) as root:md=json.loads(str(root["metadata"]))
        md["input_md5"]="wrong";metadata(response,"metadata",md)
    elif case in ("missing_event","unavailable_track"):
        rows=[]
        for i in range(5):rows.append(dict(run=7,event=i,aborted=0,total_edep_MeV=0.,bgo_edep_MeV=0.,steps=0,hit_steps=0,status="diagnostic_complete",tracks=int(i==0),input_status=0,response_status=0,tracking_unsupported=0,tracking_status=0))
        if case=="missing_event":rows.pop()
        else:rows[0].update(status="unsupported_tracking",tracking_unsupported=1)
        root=ROOT.TFile(str(cylinders),"UPDATE");root.Delete("cylinder_events;*");put_tree(root,"cylinder_events",dict(run="int32",event="int32",aborted="int32",total_edep_MeV="float64",bgo_edep_MeV="float64",steps="uint64",hit_steps="uint64",status="string",tracks="uint64",input_status="int32",response_status="int32",tracking_unsupported="int32",tracking_status="int32"),rows);root.Close()
    elif case in ("digit_duplicate","digit_range"):
        digits=[dict(run=7,event=0,channel=225,adc=200)]
        if case=="digit_duplicate":digits*=2
        else:digits[0]["channel"]=481
        root=ROOT.TFile(str(response),"UPDATE");root.Delete("bgo_digits;*");put_tree(root,"bgo_digits",dict(run="int32",event="int32",channel="int32",adc="int32"),digits);root.Close()
    elif case=="track_index":
        root=ROOT.TFile(str(cylinders),"UPDATE");root.Delete("cylinder_tracks;*");put_tree(root,"cylinder_tracks",dict(run="int32",event="int32",track_index="uint64",theta_deg="float64",phi_deg="float64"),[dict(run=7,event=0,track_index=1,theta_deg=90.,phi_deg=0.)]);root.Close()
    elif case in ("config_type","config_index","json_type"):
        with uproot.open(config) as root:md=json.loads(str(root["metadata"]))
        if case=="json_type":md["schema"]=True;metadata(config,"metadata",md)
        else:
            with uproot.open(config) as root:data=root["theta"].arrays(library="np")
            if case=="config_index":data["index"][0]=2
            root=ROOT.TFile(str(config),"UPDATE");root.Delete("theta;*")
            put_tree(root,"theta",dict(index="int32",theta="float64" if case=="config_type" else "float32",volume="float32"),[{k:data[k][i].item() for k in data} for i in range(15)]);root.Close()
    else:
        with uproot.update(response) as root:root["summary"]="{}"
    p=run(native,paths,tmp_path/"out")
    assert p.returncode==1 and not (tmp_path/"out/central.root").exists(),p.stderr


def test_launcher_binds_sources_configuration_and_upstream_provenance(native,tmp_path):
    paths=fixtures(tmp_path);path=launcher.reconstruct(*paths,tmp_path/"launch",native,123)
    with uproot.open(path.parent/"provenance.root") as root:p=json.loads(str(root["metadata"]))
    assert p["result_sha256"]==launcher.sha256(path)
    assert p["transport_sha256"]==launcher.sha256(paths[0])
    assert p["configuration"]["initialization_claim"].startswith("Synthetic")
    assert p["upstream"]["response"]["mode"]=="legacy09_diagnostic"
    assert p["upstream"]["cylinders"]["mode"]=="selected26_old_cyl_diagnostic"
    assert p["physical_validation"] is False
    with pytest.raises(FileExistsError):launcher.reconstruct(*paths,tmp_path/"launch",native,123)


@pytest.mark.parametrize("case",["response_provenance","producer_config","configuration","source","log","provenance","publication"])
def test_launcher_measured_identity_and_failed_publication(native,tmp_path,monkeypatch,case):
    paths=fixtures(tmp_path)
    if case=="response_provenance":
        with uproot.open(paths[1].parent/"provenance.root") as root:p=json.loads(str(root["metadata"]))
        p["input_sha256"]="1"*64;metadata(paths[1].parent/"provenance.root","metadata",p)
    elif case=="producer_config":
        with (paths[1].parent/"producer_config.root").open("ab") as f:f.write(b"changed")
    elif case in ("configuration","source"):
        mutable=tmp_path/"current.hh";mutable.write_text("before")
        if case=="source":
            old=launcher._source_files;monkeypatch.setattr(launcher,"_source_files",lambda:old()+[mutable])
        oldrun=launcher.subprocess.run
        def change(args,**kwargs):
            result=oldrun(args,**kwargs)
            target=paths[3] if case=="configuration" else mutable
            with target.open("ab") as f:f.write(b"changed")
            return result
        monkeypatch.setattr(launcher.subprocess,"run",change)
    elif case in ("log","provenance"):
        def fail(*args):raise OSError("injected checked write failure")
        monkeypatch.setattr(launcher,"_exclusive_text" if case=="log" else "_write_provenance",fail)
    else:
        old=Path.rename
        def fail(path,target):
            if path.name=="central.pending":raise OSError("injected publication failure")
            return old(path,target)
        monkeypatch.setattr(Path,"rename",fail)
    with pytest.raises((OSError,ValueError,RuntimeError)):launcher.reconstruct(*paths,tmp_path/"launch",native,123)
    assert not (tmp_path/"launch/central").exists()
    assert not (tmp_path/"launch/central.pending/central.root").exists()


def test_unavailable_barrel_keeps_ca_but_cannot_classify_bgo_as_no_barrel(native,tmp_path):
    paths=fixtures(tmp_path);response=paths[1]
    ledger=table(response,"response_events");digits=table(response,"barrel_digits")
    ledger["status"][3]="unsupported_barrel_record_overflow";ledger["barrel_digits"][3]=0
    rows=[{k:(v[i].item() if hasattr(v[i],"item") else v[i]) for k,v in ledger.items()} for i in range(5)]
    barrel=[{k:int(v[i]) for k,v in digits.items()} for i in range(len(digits["run"])) if digits["event"][i]!=3]
    root=ROOT.TFile(str(response),"UPDATE")
    try:
        root.Delete("response_events;*");root.Delete("barrel_digits;*")
        put_tree(root,"response_events",dict(run="int32",event="int32",aborted="int32",total_edep_MeV="float64",bgo_edep_MeV="float64",steps="uint64",hit_steps="uint64",status="string",bgo_digits="int32",barrel_digits="int32"),rows)
        put_tree(root,"barrel_digits",dict(run="int32",event="int32",channel="int32",adc="int32",tdc="int32"),barrel)
    finally:root.Close()
    result=run(native,paths,tmp_path/"out");assert result.returncode==0,result.stderr
    path=tmp_path/"out/central.root";events=table(path,"central_events")
    assert events["ca_called"][3]==1 and events["ca_clusters"][3]==1
    assert events["bgo_measurements_available"][3]==0 and events["bgo_status"][3]==-1
    assert events["association_available"][3]==0 and events["association_status"][3]==-1
    assert events["good_bgo"][3]==0 and len(events["run"])==5
    assert 3 in table(path,"central_ca_members")["event"]


def test_physical_bgo_copy_mapping_is_distinct_from_fortran_grid_offset(native,tmp_path):
    paths=fixtures(tmp_path);response=paths[1]
    # Independent producer API: physical theta rings contain32 successive phi
    # copies; CA's EDEPTH memory stride15 must never become a physical ID.
    channels=list(range(1,481))
    ledger=table(response,"response_events");ledger["bgo_digits"][0]=len(channels)
    rows=[{k:(v[i].item() if hasattr(v[i],"item") else v[i]) for k,v in ledger.items()} for i in range(5)]
    original=table(response,"bgo_digits")
    digits=[dict(run=7,event=0,channel=ch,adc=10) for ch in channels]
    digits.extend({k:int(v[i]) for k,v in original.items()} for i in range(len(original["run"])) if original["event"][i]!=0)
    root=ROOT.TFile(str(response),"UPDATE")
    try:
        root.Delete("response_events;*");root.Delete("bgo_digits;*")
        put_tree(root,"response_events",dict(run="int32",event="int32",aborted="int32",total_edep_MeV="float64",bgo_edep_MeV="float64",steps="uint64",hit_steps="uint64",status="string",bgo_digits="int32",barrel_digits="int32"),rows)
        put_tree(root,"bgo_digits",dict(run="int32",event="int32",channel="int32",adc="int32"),digits)
    finally:root.Close()
    result=run(native,paths,tmp_path/"out");assert result.returncode==0,result.stderr
    grid=table(tmp_path/"out/central.root","central_bgo_grid");select=grid["event"]==0
    assert grid["channel"][select].tolist()==channels
    expected=[bgo_electronics(ch) for ch in channels]
    assert grid["theta"][select].tolist()==[v["theta_index"] for v in expected]
    assert grid["phi"][select].tolist()==[v["phi_index"] for v in expected]
    for ch,theta,phi in zip(grid["channel"],grid["theta"],grid["phi"]):
        assert ch==32*(theta-1)+phi
    members=table(tmp_path/"out/central.root","central_ca_members")
    for channel,member in zip(members["channel"],members["crystal_id"]):
        index=bgo_electronics(int(channel))
        assert member==100*index["theta_index"]+index["phi_index"]


@pytest.mark.parametrize("field",["bgo_adc_channels","bgo_adc_fullscale_gev","barrel_adc_channels","barrel_adc_fullscale_gev","barrel_tdc_channels","barrel_tdc_fullscale_seconds"])
def test_decoding_scales_must_equal_actual_producer_configuration(native,tmp_path,field):
    paths=fixtures(tmp_path);config=paths[3]
    with uproot.open(config) as root:
        md=json.loads(str(root["metadata"]));scalars=root["scalars"].arrays(library="np")
    scalars[field][0]*=2;md["scalars"][field]=float(scalars[field][0])
    with uproot.update(config) as root:
        del root["scalars"]
        root.mktree("scalars",{k:v.dtype for k,v in scalars.items()}).extend(scalars)
    metadata(config,"metadata",md)
    result=run(native,paths,tmp_path/"out")
    assert result.returncode==1 and "producer decode scale mismatch" in result.stderr
    assert not (tmp_path/"out/central.root").exists()
    with pytest.raises(RuntimeError,match="producer decode scale mismatch"):
        launcher.reconstruct(*paths,tmp_path/"launch",native,123)
    assert not (tmp_path/"launch/central").exists()
