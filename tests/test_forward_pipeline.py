"""Real ROOT measured-only forward composition and transactional publication."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest
import uproot
from tests.test_digitize import ROOT, SCHEMAS, STEP_INTS, STEP_DOUBLES, STEP_STRINGS, put_tree, table
from mc_simulation.geant4 import forward as launcher
from mc_simulation.geant4.forward_reconstruction_config import write_forward_reconstruction_config

DATA = Path(__file__).resolve().parents[1]/"docs/reference/fortran/prog/data"


def step(detector, channel=8, event=0, energy=0., **changes):
    row={**dict.fromkeys(STEP_INTS,0),**dict.fromkeys(STEP_DOUBLES,0.),**dict.fromkeys(STEP_STRINGS,"")}
    row.update(run=7,event=event,track=1,track_step=1,track_weight=1.,path=f"/LAGR:1/{detector}:{channel}",
               edep_MeV=energy,pre_time_ns=20.,post_time_ns=21.,post_x_mm=35.,post_y_mm=45.,material="fixture")
    row.update(changes)
    return row


def fixtures(steps=None, events=3):
    channels=[]
    for volume,role,name,count in (("H",3,"tof_h",26),("V",4,"tof_v",26),("S",5,"shower",16)):
        for ch in range(1,count+1):
            channels.append(dict(path=f"/LAGR:1/{volume}:{ch}",detector=name,sensitive=role,volume=volume,copy=ch,
                                 legacy_channel=ch,channel_kind="legacy_scintillator",medium=1,material_id=1,material="fixture"))
    rows=[step("H",energy=80),step("V",energy=80),step("S",energy=20),step("H",event=2,energy=.001)] if steps is None else steps
    ledger=[]
    for event in range(events):
        hits=[r for r in rows if r["event"]==event]
        for i,row in enumerate(hits):row["track_step"]=i+1
        ledger.append(dict(run=7,event=event,total_edep_MeV=sum(r["edep_MeV"] for r in hits),bgo_edep_MeV=0.,steps=len(hits),hit_steps=len(hits),aborted=0))
    return dict(channels=channels,events=ledger,detector_steps=rows,primaries=[])


def write_input(path, rows=None, summary=None, schemas=None):
    rows=fixtures() if rows is None else rows
    md=dict(status="diagnostic_transport_only",hit_schema_version=2,aborted=0,events=len(rows["events"]),attempted_events=len(rows["events"]),
            all_callbacks=sum(r["steps"] for r in rows["events"]),passive_callbacks=0,detector_steps=len(rows["detector_steps"]))
    md.update(summary or {})
    f=ROOT.TFile(str(path),"CREATE")
    try:
        for name,schema in (schemas or SCHEMAS).items():put_tree(f,name,schema,rows[name])
        f.cd();assert ROOT.TObjString(json.dumps(md)).Write("summary")>0
    finally:f.Close()
    return path


def tracking(path,source,rows,changes=None,tracks=None):
    ledger=[]
    for row in rows["events"]:
        ledger.append(dict(row,status="diagnostic_no_track",kernel_status=0,digit_status=0,reconstruction_status=0,ntracks=0))
    if changes: changes(ledger)
    f=ROOT.TFile(str(path),"CREATE")
    try:
        put_tree(f,"tracking_events",dict(run="int32",event="int32",aborted="int32",steps="uint64",hit_steps="uint64",total_edep_MeV="float64",bgo_edep_MeV="float64",status="string",kernel_status="int32",digit_status="int32",reconstruction_status="int32",ntracks="int32"),ledger)
        put_tree(f,"planar_tracks",dict(run="int32",event="int32",track_index="int32",first_x_cm="float64",first_y_cm="float64",first_z_cm="float64",second_x_cm="float64",second_y_cm="float64",second_z_cm="float64",cl="int32"),tracks or [])
        f.cd();ROOT.TObjString(json.dumps(dict(schema_version=1,mode="selected26_newplan_diagnostic",input_md5=hashlib.md5(source.read_bytes()).hexdigest(),physical_validation=False))).Write("metadata")
        ROOT.TObjString(json.dumps(dict(schema_version=1,status="selected26_newplan_diagnostic_complete",events=len(ledger),detector_steps=len(rows["detector_steps"]),tracks=len(tracks or [])))).Write("summary")
    finally:f.Close()
    return path


@pytest.fixture
def native():
    path=os.environ.get("GRAAL_FORWARD_EXE")
    if not path:pytest.skip("Set GRAAL_FORWARD_EXE for native forward ROOT tests")
    assert Path(path).is_file()
    return Path(path)


@pytest.fixture
def config(tmp_path):
    path=tmp_path/"config.root";write_forward_reconstruction_config(DATA,path,source_run=1321);return path


def run(native,source,tracks,config,output):
    return subprocess.run([str(x) for x in (native,source,tracks,config,output,123)],capture_output=True,text=True,timeout=60)


def setup(tmp_path,rows=None,summary=None,schemas=None):
    rows=fixtures() if rows is None else rows
    source=write_input(tmp_path/"input.root",rows,summary,schemas)
    return source,tracking(tmp_path/"tracking.root",source,rows)


def replace_metadata(path,name,value):
    root=ROOT.TFile(str(path),"UPDATE")
    try:root.cd();assert ROOT.TObjString(value if isinstance(value,str) else json.dumps(value)).Write(name,ROOT.TObject.kOverwrite)>0
    finally:root.Close()


def test_complete_nohit_threshold_source_links_and_replay(native,config,tmp_path):
    source,tracks=setup(tmp_path)
    for name in ("one","two"):
        result=run(native,source,tracks,config,tmp_path/name);assert result.returncode==0,result.stderr
    path=tmp_path/"one/forward.root";e=table(path,"forward_events")
    assert e["event"].tolist()==[0,1,2]
    assert e["wall_response_available"].tolist()==[1,1,1]
    assert e["wall_h_accepted"].tolist()==[1,0,0]
    assert e["wall_v_accepted"].tolist()==[1,0,0]
    assert e["wall_reconstruction_status"].tolist()==[0,0,0]
    assert e["association_status"].tolist()==[0,0,0]
    links=table(path,"forward_compact_links")
    assert links["source_step_entry"].tolist()==[0,1,2,3]
    compact=table(path,"forward_compact")
    assert compact["position_cm"].tolist()==[3.5,4.5,4.5,3.5]
    with uproot.open(path) as root:
        assert json.loads(str(root["metadata"]))["source_run"]==1321
        for name,kind in root.classnames(cycle=False).items():
            if kind=="TTree":
                a,b=table(path,name),table(tmp_path/"two/forward.root",name)
                for key in a:assert np.array_equal(a[key],b[key]),(name,key)
    # Wall and shower source-object references resolve through measured digit rows.
    ds=table(path,"forward_digits")
    for event,det,index in zip(table(path,"wall_hits")["event"],table(path,"wall_hits")["detector"],table(path,"wall_hits")["digit_index"]):
        assert index<sum((ds["event"]==event)&(ds["detector"]==det))


@pytest.mark.parametrize("case",["counterpart","overflow","partial_time","planar_unavailable"])
def test_unsupported_remains_all_event_distinct_from_rejection(native,config,tmp_path,case):
    rows=fixtures([step("V",energy=80)]) if case=="counterpart" else fixtures()
    if case=="overflow":rows=fixtures([step("H",energy=80,post_x_mm=float(i*100)) for i in range(101)])
    if case=="partial_time":
        rows=fixtures([step("H",energy=80,pre_time_ns=0.,post_time_ns=0.)])
        # Valid matching config with negative timing offset exposes source partial-write domain.
        with uproot.open(config) as f:md=json.loads(str(f["metadata"]));a=f["wall"].arrays(library="np")
        a["tdcoffset"][:]=-10000;md["wall"]["tdcoffset"]=[float(x) for x in a["tdcoffset"]]
        f=ROOT.TFile(str(config),"UPDATE");f.Delete("wall;*");put_tree(f,"wall",{k:"float32" for k in a},[{k:float(a[k][i]) for k in a} for i in range(110)]);f.Close();replace_metadata(config,"metadata",md)
    source,tracks=setup(tmp_path,rows)
    if case=="planar_unavailable":
        tracks.unlink();tracking(tracks,source,rows,lambda a:a[0].update(status="unsupported_kernel_domain",kernel_status=8,digit_status=8))
    result=run(native,source,tracks,config,tmp_path/"out");assert result.returncode==0,result.stderr
    e=table(tmp_path/"out/forward.root","forward_events")
    assert len(e["event"])==3 and e["association_status"][0]!=0
    if case=="planar_unavailable":assert e["wall_response_available"][0]==1
    else:assert e["wall_response_available"][0]==0 and e["wall_h_accepted"][0]==0
    if case=="overflow":assert len(table(tmp_path/"out/forward.root","forward_compact_links")["source_step_entry"])==101


@pytest.mark.parametrize("case",["inventory","duplicate","event_order","steps","negative","nonfinite","status","native_string","schema_type","join","track_status","track_index","config_integer","json_duplicate","root_cycle"])
def test_malformed_input_has_no_consumable_success(native,config,tmp_path,case):
    rows=fixtures();summary={};schemas=copy.deepcopy(SCHEMAS)
    if case=="inventory":rows["channels"].pop()
    elif case=="duplicate":rows["channels"].append(rows["channels"][0])
    elif case=="event_order":rows["events"].reverse()
    elif case=="steps":rows["events"][0]["hit_steps"]-=1
    elif case=="negative":rows["detector_steps"][0]["edep_MeV"]=-1
    elif case=="nonfinite":rows["detector_steps"][0]["post_y_mm"]=float("nan")
    elif case=="status":rows["detector_steps"][0]["track_status"]=6
    elif case=="native_string":rows["detector_steps"][0]["process"]="bad\0hidden"
    elif case=="schema_type":schemas["detector_steps"]["post_x_mm"]="float32"
    source,tracks=setup(tmp_path,rows,summary,schemas)
    if case=="join":
        with uproot.open(tracks) as f:md=json.loads(str(f["metadata"]))
        md["input_md5"]="different";replace_metadata(tracks,"metadata",md)
    elif case=="track_status":
        tracks.unlink();tracking(tracks,source,rows,lambda a:a[0].update(kernel_status=1))
    elif case=="track_index":
        tracks.unlink();tracking(tracks,source,rows,tracks=[dict(run=7,event=0,track_index=1,first_x_cm=0.,first_y_cm=0.,first_z_cm=94.4,second_x_cm=0.,second_y_cm=0.,second_z_cm=134.4,cl=0)])
    elif case in ("config_integer","json_duplicate"):
        with uproot.open(config) as f:md=json.loads(str(f["metadata"]))
        if case=="config_integer":md["reconstruction"]["source_run"]=1321.5
        replace_metadata(config,"metadata",json.dumps(md) if case=="config_integer" else json.dumps(md)[:-1]+',"schema":1}')
    elif case=="root_cycle":
        with uproot.update(source) as f:f["summary"]="{}"
    result=run(native,source,tracks,config,tmp_path/"out")
    assert result.returncode==1,(case,result.stderr)
    assert not (tmp_path/"out/forward.root").exists()


@pytest.mark.parametrize("field",["events","attempted_events","all_callbacks","passive_callbacks","detector_steps","hit_schema_version","aborted"])
@pytest.mark.parametrize("value",[.5,1.0,-1,True,2**64])
def test_json_counter_categories_strict(native,config,tmp_path,field,value):
    summary={field:value}
    if field=="events":summary["attempted_events"]=value
    source,tracks=setup(tmp_path,summary=summary)
    result=run(native,source,tracks,config,tmp_path/"out")
    assert result.returncode==1 and "JSON integer" in result.stderr


def test_launcher_hashes_nooverwrite(native,tmp_path):
    source,tracks=setup(tmp_path)
    response=launcher.reconstruct(source,tracks,DATA,tmp_path/"launch",native,123,source_run=1321)
    with uproot.open(response.parent/"provenance.root") as f:p=json.loads(str(f["metadata"]))
    for key,path in (("input",source),("tracking",tracks),("executable",native),("response",response),("config",response.parent.parent/"forward_config.root")):
        assert p[key+"_sha256"]==launcher.sha256(path)
    assert any(x.endswith("ForwardSourceKernels.hh") for x in p["code_sha256"])
    with pytest.raises(FileExistsError):launcher.reconstruct(source,tracks,DATA,tmp_path/"launch",native,123,source_run=1321)


@pytest.mark.parametrize("case",["log","provenance","input","tracking","config","source","binary","publication"])
def test_launcher_failure_invalidates_pending(native,tmp_path,monkeypatch,case):
    source,tracks=setup(tmp_path);mutable=tmp_path/"mutable.hh";mutable.write_text("before")
    if case=="source":
        old=launcher._source_files;monkeypatch.setattr(launcher,"_source_files",lambda:old()+[mutable])
    if case=="binary":
        target=tmp_path/"exe";shutil.copy2(native,target);native=target
    if case in ("log","provenance"):
        def fail(*args):raise OSError("injected write failure")
        monkeypatch.setattr(launcher,"_exclusive_text" if case=="log" else "_write_provenance",fail)
    elif case=="publication":
        rename=Path.rename
        def fail(path,target):
            if path.name=="forward.pending":raise OSError("injected publication failure")
            return rename(path,target)
        monkeypatch.setattr(Path,"rename",fail)
    else:
        oldrun=launcher.subprocess.run
        def change(args,**kwargs):
            result=oldrun(args,**kwargs)
            target={"input":source,"tracking":tracks,"config":Path(args[3]),"source":mutable,"binary":native}[case]
            with target.open("ab") as f:f.write(b"changed")
            return result
        monkeypatch.setattr(launcher.subprocess,"run",change)
    with pytest.raises((OSError,RuntimeError)):launcher.reconstruct(source,tracks,DATA,tmp_path/"launch",native,123,source_run=1321)
    assert not (tmp_path/"launch/forward").exists()
    assert not (tmp_path/"launch/forward.pending/forward.root").exists()
    assert (tmp_path/"launch/forward.pending/forward.invalid.root").exists()


@pytest.mark.parametrize("field",["schema","source_run","rf_bunch"])
@pytest.mark.parametrize("value",[.5,0.0,-1,True,2**64])
def test_config_integers_require_categories_before_conversion(native,config,tmp_path,field,value):
    with uproot.open(config) as f:md=json.loads(str(f["metadata"]))
    (md if field=="schema" else md["reconstruction"])[field]=value
    replace_metadata(config,"metadata",md)
    source,tracks=setup(tmp_path)
    result=run(native,source,tracks,config,tmp_path/"out")
    assert result.returncode==1 and "JSON integer" in result.stderr


def test_source_mutated_during_provenance_write_cannot_publish(native,tmp_path,monkeypatch):
    source,tracks=setup(tmp_path);mutable=tmp_path/"source.hh";mutable.write_text("before")
    old=launcher._source_files;monkeypatch.setattr(launcher,"_source_files",lambda:old()+[mutable])
    write=launcher._write_provenance
    def mutate(path,provenance):
        write(path,provenance);mutable.write_text("after")
    monkeypatch.setattr(launcher,"_write_provenance",mutate)
    with pytest.raises(RuntimeError,match="source changed"):
        launcher.reconstruct(source,tracks,DATA,tmp_path/"launch",native,123,source_run=1321)
    assert not (tmp_path/"launch/forward").exists()
    assert (tmp_path/"launch/forward.pending/forward.invalid.root").is_file()


def test_partial_native_nooverwrite_and_existing_log(native,config,tmp_path,monkeypatch):
    source,tracks=setup(tmp_path)
    output=tmp_path/"existing";output.mkdir();(output/"sentinel").write_text("preserved")
    result=run(native,source,tracks,config,output)
    assert result.returncode==1 and (output/"sentinel").read_text()=="preserved"
    partial=source.rename(tmp_path/"input.partial.root")
    result=run(native,partial,tracks,config,tmp_path/"out")
    assert result.returncode==1 and "Partial" in result.stderr
    source=partial.rename(source)
    old=launcher.subprocess.run
    def existing(args,**kwargs):
        result=old(args,**kwargs);(Path(args[4]).parent/"native.log").write_text("preserved");return result
    monkeypatch.setattr(launcher.subprocess,"run",existing)
    with pytest.raises(FileExistsError):launcher.reconstruct(source,tracks,DATA,tmp_path/"launch",native,123,source_run=1321)
    assert (tmp_path/"launch/native.log").read_text()=="preserved"
    assert (tmp_path/"launch/forward.pending/forward.invalid.root").exists()


def test_unrecognized_shower_serializes_each_source_energy_unit(native,config,tmp_path):
    # Small measured deposits produce both ordinary low-energy and source
    # zero-product fallback records under the fixed diagnostic normal stream.
    rows=fixtures([step("S",event=i,energy=.5) for i in range(32)],events=32)
    source,tracks=setup(tmp_path,rows)
    result=run(native,source,tracks,config,tmp_path/"out");assert result.returncode==0,result.stderr
    path=tmp_path/"out/forward.root";unrecognized=table(path,"shower_unrecognized");digits=table(path,"forward_digits")
    assert set(unrecognized["energy_fallback_MeV"])=={0,1}
    with uproot.open(config) as f:ae=f["simulation_rw"]["ae"].array(library="np")
    for event,index,channel,energy,fallback in zip(unrecognized["event"],unrecognized["digit_index"],unrecognized["channel"],unrecognized["energy"],unrecognized["energy_fallback_MeV"]):
        select=(digits["event"]==event)&(digits["detector"]==2)&(digits["digit_index"]==index)
        assert select.sum()==1
        up,down=int(digits["adc1"][select][0]),int(digits["adc2"][select][0])
        assert bool(fallback)==(up==0 or down==0)
        if fallback:expected=.5*float(ae[channel-1])*(up+down)
        else:expected=float(ae[channel-1])*np.sqrt(up*down)*1e-3
        assert energy==pytest.approx(expected,rel=2e-6,abs=1e-12)
