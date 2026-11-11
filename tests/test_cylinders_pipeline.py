"""Strict real-ROOT central stream composition; fixtures are diagnostic only."""
import copy
import json
import math
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import uproot
from tests.test_digitize import ROOT, SCHEMAS as BASE_SCHEMAS, STEP_INTS, STEP_DOUBLES, STEP_STRINGS, put_tree, table
from mc_simulation.geant4 import cylinders as launcher
from mc_simulation.geant4.cylinder_config import write_cylinder_config

DATA = Path(__file__).resolve().parents[1] / "docs/reference/fortran/prog/data"
SCHEMAS = copy.deepcopy(BASE_SCHEMAS)
SCHEMAS["cylinder_step_context"] = dict(run="int32", event="int32", source_step_entry="uint64", callback_index="uint64", passive_epoch="uint64")
CONTEXT = dict(schema_version=1, scope="all_central_sensitive_steps", source_tree="detector_steps", source_entry_origin=0,
               callback_origin=0, passive_epoch_origin="0_unknown", counter_scope="output_stream_across_tracks_events_runs",
               reset_rule="every_callback_with_sensitivity_outside_1_to_14", legacy_source="laggen/src/gustep.F",
               legacy_source_sha256="e5fb4bb8474ec8f657241b678f1c0661a0a30a7617a8a31136ed64f9141ec660", physical_validation=False)
ROLES = {"CYL1":(6,"cyl_surface_1"), "CYL2":(7,"cyl_surface_2"), "CYG1":(10,"cyl_gas_1"),
         "CYG2":(10,"cyl_gas_1"), "CYG3":(11,"cyl_gas_2"), "CYG4":(11,"cyl_gas_2")}


def step(volume, event=0, **changes):
    row = {**dict.fromkeys(STEP_INTS,0), **dict.fromkeys(STEP_DOUBLES,0.), **dict.fromkeys(STEP_STRINGS,"")}
    radius = 50. if volume in ("CYL1","CYG1","CYG2") else 85.
    row.update(run=7,event=event,track=1,track_step=1,track_weight=1.,charge_e=1.,pre_boundary=1,
               path=f"/LAGR:1/{volume}:1",pre_x_mm=radius*math.cos(.4),pre_y_mm=radius*math.sin(.4),material="fixture")
    row.update(changes)
    return row


def fixtures(steps=None, passive=None, events=3):
    rows = ([step("CYG1", edep_MeV=1.),step("CYL1"),step("CYG2",edep_MeV=2.),
             step("CYL2"),step("CYG4",edep_MeV=2.),step("CYL1",event=2)] if steps is None else steps)
    passive = {0:1,1:2} if passive is None else passive
    channels = [dict(path=f"/LAGR:1/{v}:1", detector=d,sensitive=r,volume=v,copy=1,legacy_channel=1,
                     channel_kind="chamber_surface" if r in (6,7) else "gas_volume",medium=1,material_id=1,material="fixture") for v,(r,d) in ROLES.items()]
    ledger, context, epoch, offset = [],[],0,0
    for event in range(events):
        hits = [r for r in rows if r["event"]==event]
        epoch += passive.get(event,0)
        for local,row in enumerate(hits):
            row["track_step"] = local+1
            context.append(dict(run=7,event=event,source_step_entry=offset,callback_index=offset+epoch,passive_epoch=epoch))
            offset += 1
        ledger.append(dict(run=7,event=event,total_edep_MeV=sum(r["edep_MeV"] for r in hits),bgo_edep_MeV=0.,steps=len(hits)+passive.get(event,0),hit_steps=len(hits),aborted=0))
    return dict(channels=channels,events=ledger,detector_steps=rows,primaries=[],cylinder_step_context=context)


def write_input(path, rows=None, *, summary=None, context=None, schemas=None):
    rows = fixtures() if rows is None else rows
    metadata = dict(status="diagnostic_transport_only",hit_schema_version=2,aborted=0,events=len(rows["events"]),attempted_events=len(rows["events"]),
                    detector_steps=len(rows["detector_steps"]),cylinder_context_schema=1,cylinder_context_rows=len(rows["cylinder_step_context"]),
                    all_callbacks=sum(e["steps"] for e in rows["events"]),passive_callbacks=sum(e["steps"]-e["hit_steps"] for e in rows["events"]))
    metadata.update(summary or {})
    root = ROOT.TFile(str(path),"CREATE")
    assert root.IsOpen() and not root.IsZombie()
    try:
        for name,schema in (schemas or SCHEMAS).items():
            put_tree(root,name,schema,rows[name])
        root.cd()
        assert ROOT.TObjString(json.dumps(metadata)).Write("summary")>0
        if context is not False:
            assert ROOT.TObjString(json.dumps(CONTEXT if context is None else context)).Write("cylinder_context_metadata")>0
    finally:
        root.Close()
    return path


@pytest.fixture
def native():
    value = os.environ.get("GRAAL_CYLINDERS_EXE")
    if not value:
        pytest.skip("Set GRAAL_CYLINDERS_EXE for native central ROOT composition")
    assert Path(value).is_file()
    return Path(value)


@pytest.fixture
def config(tmp_path):
    path = tmp_path/"config.root"
    write_cylinder_config(DATA,path)
    return path


def run(native, source, config, output, seed=123):
    return subprocess.run([str(native),str(source),str(config),str(output),str(seed)],capture_output=True,text=True,timeout=60)


def test_complete_source_charge_links_nohit_floor_and_seed_replay(native,config,tmp_path):
    source = write_input(tmp_path/"input.root")
    for name in ("one","two"):
        result = run(native,source,config,tmp_path/name)
        assert result.returncode==0,result.stderr
    response = tmp_path/"one/cylinders.root"
    events = table(response,"cylinder_events")
    assert events["event"].tolist()==[0,1,2]
    assert events["status"].tolist()==["diagnostic_complete"]*3
    assert events["normal_draws"].tolist()==[318,316,317]
    assert events["passive_callbacks"].tolist()==[1,2,0]
    assert events["raw_inner"].tolist()==[1,0,1]
    assert events["raw_outer"].tolist()==[1,0,0]
    crossings = table(response,"cylinder_crossings")
    assert crossings["source_step_entry"].tolist()==[1,3,5]
    assert crossings["floor_applied"].tolist()==[0,0,1]
    assert crossings["raw_gas_GeV"].tolist()==pytest.approx([.003,.002,0.],rel=1e-6)
    assert crossings["digitizer_GeV"][-1]==float(np.float32(1e-7))
    links = table(response,"cylinder_gas_links")
    assert links["source_step_entry"].tolist()==[0,2,4]
    assert links["target_crossing"].tolist()==[0,0,1]
    assert links["target_valid"].tolist()==[1,1,1]
    assert links["disposition"].tolist()==[1,1,1]
    assert crossings["contribution_count"].tolist()==[2,1,0]
    assert len(table(response,"cylinder_strip_charges")["strip"])==3*316
    with uproot.open(response) as root:
        metadata=json.loads(str(root["metadata"]))
        assert metadata["physics_validation"] is False
        assert "wire identifiers and strip ADC" in metadata["tracker_input"]
        names=[k for k,v in root.classnames(cycle=False).items() if v=="TTree"]
    for name in names:
        first,second=table(response,name),table(tmp_path/"two/cylinders.root",name)
        for key in first:
            assert np.array_equal(first[key],second[key]),(name,key)
    # Every reconstruction reference resolves to a measured digit or association.
    wire_digits=table(response,"cylinder_wires")
    for group in table(response,"cylinder_wire_groups")["digit_index"]:
        assert group<len(wire_digits["wire"])
    cluster_links=table(response,"cylinder_cluster_links")
    digit_rows=table(response,"cylinder_cathodes")
    for event,p,digit in zip(cluster_links["event"],cluster_links["cathode"],cluster_links["digit_index"]):
        assert digit < np.sum((digit_rows["event"]==event)&(digit_rows["cathode"]==p))


@pytest.mark.parametrize("events",[0,3])
def test_empty_input_preserves_each_event_and_noise(native,config,tmp_path,events):
    source=write_input(tmp_path/"empty.root",fixtures([],passive={},events=events))
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==0,result.stderr
    response=tmp_path/"out/cylinders.root"
    assert table(response,"cylinder_events")["event"].tolist()==list(range(events))
    assert table(response,"cylinder_events")["normal_draws"].tolist()==[316]*events
    assert len(table(response,"cylinder_tracks")["run"])==0


@pytest.mark.parametrize("case",["cross_event_assignment","passive_discard","unresolved","unknown","invalid_index","overflow"])
def test_saved_state_cross_event_and_unsupported_never_track(native,config,tmp_path,case):
    if case=="overflow":
        rows=fixtures([step("CYL1") for _ in range(21)],passive={0:1},events=1)
    else:
        steps=[step("CYG1",edep_MeV=1.),step("CYL1",event=1),step("CYG2",event=1,edep_MeV=2.)]
        passive={0:1}
        if case=="passive_discard": passive[1]=1
        if case=="unresolved": steps=steps[:1]
        if case=="unknown": passive={}
        if case=="invalid_index": steps=[step("CYL1"),step("CYG4",edep_MeV=1.)]
        rows=fixtures(steps,passive=passive,events=2)
    source=write_input(tmp_path/"input.root",rows)
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==0,result.stderr
    response=tmp_path/"out/cylinders.root"
    ledger=table(response,"cylinder_events")
    gas=table(response,"cylinder_gas_links")
    if case=="cross_event_assignment":
        assert gas["target_event"].tolist()==[1,1]
        assert ledger["cross_event_assigned_GeV"][0]==pytest.approx(.001)
        assert ledger["imported_pending_GeV"][1]==pytest.approx(.001)
    elif case=="passive_discard":
        assert gas["disposition"].tolist()==[2,1]
        assert ledger["discarded_pending_GeV"][0]==pytest.approx(.001)
    elif case=="unresolved": assert gas["disposition"].tolist()==[5]
    elif case=="invalid_index": assert gas["disposition"].tolist()==[3]
    elif case=="overflow": assert ledger["raw_inner"].tolist()==[21]
    if case in ("unresolved","unknown","invalid_index","overflow"):
        assert ledger["input_status"][0]!=0
        assert ledger["status"][0]=="unsupported_input"
        assert ledger["tracks"][0]==0
        assert ledger["normal_draws"][0]==0


@pytest.mark.parametrize("case",["missing_capability","missing_metadata","wrong_source","missing_context","extra_context","event_context","source_context","callback_context","epoch_context","epoch_regression","context_count","callbacks","passive","event_duplicate","event_order","orphan","step_order","track_order","unknown_path","duplicate_path","missing_inventory","wrong_volume","wrong_copy","wrong_role","aborted","schema","partial_summary","hit_count","negative_energy","nonfinite","nonfinite_pre","nonfinite_other","bad_weight","energy_sum","bgo_sum","bad_boundary","overflow_count"])
def test_corrupt_transport_rejected_without_success(native,config,tmp_path,case):
    rows=fixtures();summary={};context=None
    if case=="missing_capability": summary["cylinder_context_schema"]=0
    elif case=="missing_metadata": context=False
    elif case=="wrong_source": context=dict(CONTEXT,legacy_source_sha256="bad")
    elif case=="missing_context": rows["cylinder_step_context"].pop(1)
    elif case=="extra_context": rows["cylinder_step_context"].append(copy.deepcopy(rows["cylinder_step_context"][-1]))
    elif case=="event_context": rows["cylinder_step_context"][0]["event"]=99
    elif case=="source_context": rows["cylinder_step_context"][1]["source_step_entry"]=0
    elif case=="callback_context": rows["cylinder_step_context"][0]["callback_index"]+=1
    elif case=="epoch_context": rows["cylinder_step_context"][0]["passive_epoch"]=99
    elif case=="epoch_regression": rows["cylinder_step_context"][2].update(passive_epoch=0,callback_index=2)
    elif case=="context_count": summary["cylinder_context_rows"]=99
    elif case=="callbacks": summary["all_callbacks"]=99
    elif case=="passive": summary["passive_callbacks"]=99
    elif case=="event_duplicate": rows["events"].append(copy.deepcopy(rows["events"][0]))
    elif case=="event_order": rows["events"].reverse()
    elif case=="orphan": rows["detector_steps"][0]["event"]=99
    elif case=="step_order": rows["detector_steps"][0],rows["detector_steps"][-1]=rows["detector_steps"][-1],rows["detector_steps"][0]
    elif case=="track_order": rows["detector_steps"][1]["track_step"]=1
    elif case=="unknown_path": rows["detector_steps"][0]["path"]="/unknown:1"
    elif case=="duplicate_path": rows["channels"].append(copy.deepcopy(rows["channels"][0]))
    elif case=="missing_inventory": rows["channels"].pop()
    elif case=="wrong_volume": rows["channels"][0]["volume"]="OTHER"
    elif case=="wrong_copy": rows["channels"][0]["copy"]=2
    elif case=="wrong_role": rows["channels"][0]["detector"]="bgo"
    elif case=="aborted": rows["events"][0]["aborted"]=1
    elif case=="schema": summary["hit_schema_version"]=1
    elif case=="partial_summary": summary["attempted_events"]=99
    elif case=="hit_count": rows["events"][0]["hit_steps"]-=1
    elif case=="negative_energy": rows["detector_steps"][0]["edep_MeV"]=-1.
    elif case=="nonfinite": rows["detector_steps"][0]["edep_MeV"]=float("nan")
    elif case=="nonfinite_pre": rows["detector_steps"][0]["pre_x_mm"]=float("inf")
    elif case=="nonfinite_other": rows["detector_steps"][0]["post_dir_z"]=float("nan")
    elif case=="bad_weight": rows["detector_steps"][0]["track_weight"]=-1.
    elif case=="energy_sum": rows["events"][0]["total_edep_MeV"]=0.
    elif case=="bgo_sum": rows["events"][0]["bgo_edep_MeV"]=1.
    elif case=="bad_boundary": rows["detector_steps"][0]["pre_boundary"]=2
    elif case=="overflow_count": rows["events"][0]["steps"]=2**64-1
    source=write_input(tmp_path/"input.root",rows,summary=summary,context=context)
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1,(case,result.stderr)
    assert "ERROR:" in result.stderr
    assert not (tmp_path/"out/cylinders.root").exists()


@pytest.mark.parametrize("tree,field,kind",[("detector_steps","edep_MeV","float32"),("cylinder_step_context","passive_epoch","int32"),("events","steps","int32")])
def test_wrong_numeric_type_rejected_even_empty(native,config,tmp_path,tree,field,kind):
    schemas=copy.deepcopy(SCHEMAS);schemas[tree][field]=kind
    source=write_input(tmp_path/"empty.root",fixtures([],passive={}),schemas=schemas)
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "branch" in result.stderr


@pytest.mark.parametrize("case",["scalar_mismatch","scalar_wrong_type","config_mode","unsupported_scalar","json_duplicate","json_malformed","source_hash"])
def test_config_types_metadata_and_fixed_profile(native,config,tmp_path,case):
    with uproot.open(config) as root:
        scalars=root["scalars"].arrays(library="np")
        metadata=json.loads(str(root["metadata"]))
    if case=="scalar_mismatch": scalars["sigct"][0]=0.
    elif case=="scalar_wrong_type": scalars["nfc1"]=scalars["nfc1"].astype("float64")
    elif case=="config_mode": metadata["mode"]="legacy09_diagnostic"
    elif case=="unsupported_scalar": scalars["sigct"][0]=metadata["sigct"]=0.
    elif case=="source_hash": metadata["sources"][9]["sha256"]="bad"
    text=json.dumps(metadata)
    if case=="json_duplicate": text=text[:-1]+',"mode":"selected26_old_cyl_diagnostic"}'
    elif case=="json_malformed": text="{bad"
    with uproot.recreate(config) as root:
        root.mktree("scalars",{k:v.dtype for k,v in scalars.items()}).extend(scalars)
        root["metadata"]=text
    source=write_input(tmp_path/"input.root")
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and not (tmp_path/"out/cylinders.root").exists()


def test_only_measured_digits_affect_reconstruction(native,config,tmp_path):
    rows=fixtures([step("CYL1"),step("CYG2",edep_MeV=.0005),step("CYL2"),step("CYG4",edep_MeV=.0005)],passive={0:1},events=1)
    for name in ("first","second"):
        if name=="second":
            for i,r in enumerate(rows["detector_steps"]):
                r.update(track=10+i,parent=2,pdg=22,post_x_mm=123.,post_y_mm=456.,pre_dir_z=-.99,post_dir_x=.8)
        source=write_input(tmp_path/f"{name}.root",rows)
        result=run(native,source,config,tmp_path/name)
        assert result.returncode==0,result.stderr
    assert len(table(tmp_path/"first/cylinders.root","cylinder_tracks")["run"])==1
    for name in ("cylinder_wires","cylinder_cathodes","cylinder_tracks","cylinder_associations"):
        a,b=table(tmp_path/"first/cylinders.root",name),table(tmp_path/"second/cylinders.root",name)
        for key in a:
            assert np.array_equal(a[key],b[key]),(name,key)


def test_nooverwrite_and_partial_input(native,config,tmp_path):
    source=write_input(tmp_path/"input.partial.root")
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "Partial" in result.stderr
    source=source.rename(tmp_path/"input.root")
    output=tmp_path/"out";output.mkdir();(output/"sentinel").write_text("preserved")
    result=run(native,source,config,output)
    assert result.returncode==1 and "refusing overwrite" in result.stderr
    assert (output/"sentinel").read_text()=="preserved"


def test_launcher_sha256_root_provenance(native,tmp_path):
    source=write_input(tmp_path/"input.root")
    response=launcher.reconstruct(source,DATA,tmp_path/"launch",native,123)
    with uproot.open(response.parent/"provenance.root") as root:
        provenance=json.loads(str(root["metadata"]))
    assert provenance["input_sha256"]==launcher.sha256(source)
    assert provenance["response_sha256"]==launcher.sha256(response)
    assert provenance["config_sha256"]==launcher.sha256(response.parent.parent/"cylinder_config.root")
    assert provenance["executable_sha256"]==launcher.sha256(native)
    assert any(p.endswith("NewPlan.hh") for p in provenance["code_sha256"])
    for path,digest in {**provenance["code_sha256"],**provenance["legacy_source_sha256"]}.items():
        assert launcher.sha256(path)==digest
    with pytest.raises(FileExistsError): launcher.reconstruct(source,DATA,tmp_path/"launch",native,123)


@pytest.mark.parametrize("case",["manifest_failure","log_failure","changed_input","changed_config","changed_source","changed_binary","rename_failure"])
def test_launcher_failure_cannot_publish(native,tmp_path,monkeypatch,case):
    source=write_input(tmp_path/"input.root")
    mutable=tmp_path/"source-copy.hh";mutable.write_text("source")
    if case=="changed_source":
        real_sources=launcher._source_files
        monkeypatch.setattr(launcher,"_source_files",lambda: real_sources()+[mutable])
    if case=="changed_binary":
        import shutil
        binary=tmp_path/"native-copy";shutil.copy2(native,binary);native=binary
    if case in ("manifest_failure","log_failure"):
        def fail(*args): raise OSError("injected checked write failure")
        monkeypatch.setattr(launcher,"_write_provenance" if case=="manifest_failure" else "_exclusive_text",fail)
    elif case=="rename_failure":
        real_rename=Path.rename
        def rename(path,target):
            if path.name=="cylinders.pending": raise OSError("injected final publication failure")
            return real_rename(path,target)
        monkeypatch.setattr(Path,"rename",rename)
    else:
        real_run=launcher.subprocess.run
        def changed(args,**kwargs):
            result=real_run(args,**kwargs)
            target={"changed_input":source,"changed_config":Path(args[2]),"changed_source":mutable,"changed_binary":native}[case]
            with target.open("ab") as stream: stream.write(b"changed")
            return result
        monkeypatch.setattr(launcher.subprocess,"run",changed)
    with pytest.raises((OSError,RuntimeError)):
        launcher.reconstruct(source,DATA,tmp_path/"launch",native,123)
    assert not (tmp_path/"launch/cylinders").exists()
    assert not (tmp_path/"launch/cylinders.pending/cylinders.root").exists()
    assert (tmp_path/"launch/cylinders.pending/cylinders.invalid.root").is_file()


def test_final_passive_only_tail_discards_pending_gas(native,config,tmp_path):
    # No later central row exposes this reset: the complete event ledger proves it.
    rows=fixtures([step("CYG1",edep_MeV=1.)],passive={0:1,1:2},events=2)
    result=run(native,write_input(tmp_path/"tail.root",rows),config,tmp_path/"out")
    assert result.returncode==0,result.stderr
    response=tmp_path/"out/cylinders.root"
    gas=table(response,"cylinder_gas_links")
    assert gas["disposition"].tolist()==[2]
    assert gas["target_valid"].tolist()==[0]
    ledger=table(response,"cylinder_events")
    assert ledger["discarded_pending_GeV"][0]==pytest.approx(.001)
    assert ledger["input_status"].tolist()==[0,0]


def test_context_cannot_reference_noncentral_sensitive_row(native,config,tmp_path):
    rows=fixtures()
    rows["channels"].append(dict(path="/LAGR:1/BGO:1",detector="bgo",sensitive=1,volume="BGO",copy=1,
                                 legacy_channel=1,channel_kind="legacy_scintillator",medium=1,material_id=1,material="fixture"))
    rows["detector_steps"][0]["path"]="/LAGR:1/BGO:1"
    rows["events"][0]["bgo_edep_MeV"]=1.
    result=run(native,write_input(tmp_path/"noncentral.root",rows),config,tmp_path/"out")
    assert result.returncode==1 and "noncentral" in result.stderr
    assert not (tmp_path/"out/cylinders.root").exists()


def test_noncentral_sensitive_does_not_reset_pending_gas(native,config,tmp_path):
    rows=fixtures()
    noncentral=step("CYG1",edep_MeV=0.,path="/LAGR:1/BGO:1")
    rows["detector_steps"].insert(1,noncentral)
    rows["channels"].append(dict(path="/LAGR:1/BGO:1",detector="bgo",sensitive=1,volume="BGO",copy=1,
                                 legacy_channel=1,channel_kind="legacy_scintillator",medium=1,material_id=1,material="fixture"))
    for i,r in enumerate(rows["detector_steps"]): r["track_step"]=i+1
    for r in rows["cylinder_step_context"][1:]:
        r["source_step_entry"]+=1;r["callback_index"]+=1
    rows["events"][0]["steps"]+=1;rows["events"][0]["hit_steps"]+=1
    result=run(native,write_input(tmp_path/"noncentral.root",rows),config,tmp_path/"out")
    assert result.returncode==0,result.stderr
    assert table(tmp_path/"out/cylinders.root","cylinder_crossings")["raw_gas_GeV"][0]==pytest.approx(.003)


def test_native_std_string_required_even_empty(native,config,tmp_path):
    source=write_input(tmp_path/"strings.root",fixtures([],passive={}))
    with uproot.update(source) as root:
        # Uproot writes TLeafC strings, which are explicitly outside native schema.
        del root["detector_steps"]
        root.mktree("detector_steps",SCHEMAS["detector_steps"])
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "std::string" in result.stderr


def test_launcher_refuses_output_symlink(native,tmp_path):
    source=write_input(tmp_path/"input.root")
    target=tmp_path/"target";target.mkdir()
    output=tmp_path/"linked";output.symlink_to(target,target_is_directory=True)
    with pytest.raises(FileExistsError): launcher.reconstruct(source,DATA,output,native,123)
    assert list(target.iterdir())==[]


def test_duplicate_root_object_cycles_rejected(native,config,tmp_path):
    source=write_input(tmp_path/"duplicate.root")
    with uproot.update(source) as root:
        root["summary"]=json.dumps(dict(status="forged"))
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "Duplicate ROOT" in result.stderr


def test_source_mutation_during_provenance_write_blocks_final_publication(native,tmp_path,monkeypatch):
    source=write_input(tmp_path/"input.root")
    mutable=tmp_path/"current-source.hh";mutable.write_text("before")
    real_sources=launcher._source_files
    monkeypatch.setattr(launcher,"_source_files",lambda: real_sources()+[mutable])
    real_write=launcher._write_provenance
    def changed(path,provenance):
        real_write(path,provenance)
        mutable.write_text("after")
    monkeypatch.setattr(launcher,"_write_provenance",changed)
    with pytest.raises(RuntimeError,match="source changed"):
        launcher.reconstruct(source,DATA,tmp_path/"launch",native,123)
    assert not (tmp_path/"launch/cylinders").exists()
    assert (tmp_path/"launch/cylinders.pending/cylinders.invalid.root").is_file()


def test_existing_native_log_is_preserved_and_invalidates_pending_result(native,tmp_path,monkeypatch):
    source=write_input(tmp_path/"input.root")
    real_run=launcher.subprocess.run
    def preexisting(args,**kwargs):
        result=real_run(args,**kwargs)
        (Path(args[3]).parent/"native.log").write_text("preserve preexisting evidence")
        return result
    monkeypatch.setattr(launcher.subprocess,"run",preexisting)
    with pytest.raises(FileExistsError): launcher.reconstruct(source,DATA,tmp_path/"launch",native,123)
    assert (tmp_path/"launch/native.log").read_text()=="preserve preexisting evidence"
    assert not (tmp_path/"launch/cylinders").exists()
    assert (tmp_path/"launch/cylinders.pending/cylinders.invalid.root").is_file()


_BAD_JSON_INTEGERS = ["fractional", "float_integer", "negative", "boolean", "overflow"]


def _bad_json_integer(actual, case, *, int32=False):
    return {"fractional":actual+.5, "float_integer":float(actual), "negative":-1,
            "boolean":bool(actual), "overflow":2**31 if int32 else 2**64}[case]


@pytest.mark.parametrize("field",["events","attempted_events","all_callbacks","passive_callbacks",
                                  "detector_steps","cylinder_context_rows","hit_schema_version",
                                  "cylinder_context_schema","aborted"])
@pytest.mark.parametrize("case",_BAD_JSON_INTEGERS)
def test_summary_counts_and_schema_require_json_integers(native,config,tmp_path,field,case):
    actual=dict(events=3,attempted_events=3,all_callbacks=9,passive_callbacks=3,detector_steps=6,
                cylinder_context_rows=6,hit_schema_version=2,cylinder_context_schema=1,aborted=0)
    changes={field:_bad_json_integer(actual[field],case,int32=field in ("hit_schema_version","cylinder_context_schema","aborted"))}
    # Reproduce the original completeness bypass: equal fractional values could
    # pass equality and then both truncate to the native integer event count.
    if field=="events": changes["attempted_events"]=changes[field]
    source=write_input(tmp_path/"input.root",summary=changes)
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "JSON integer" in result.stderr
    assert not (tmp_path/"out/cylinders.root").exists()


@pytest.mark.parametrize("field",["schema_version","source_entry_origin","callback_origin"])
@pytest.mark.parametrize("case",_BAD_JSON_INTEGERS)
def test_context_schema_and_origins_require_json_integers(native,config,tmp_path,field,case):
    metadata=dict(CONTEXT)
    metadata[field]=_bad_json_integer(metadata[field],case,int32=field=="schema_version")
    source=write_input(tmp_path/"input.root",context=metadata)
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "JSON integer" in result.stderr
    assert not (tmp_path/"out/cylinders.root").exists()


@pytest.mark.parametrize("field",["schema","nf1","nf2","nfc1","nfc2","nb1","nb2","nb3","nb4","nbord"])
@pytest.mark.parametrize("case",_BAD_JSON_INTEGERS)
def test_config_integer_metadata_requires_json_integers(native,config,tmp_path,field,case):
    with uproot.open(config) as root:
        metadata=json.loads(str(root["metadata"]))
    metadata[field]=_bad_json_integer(metadata[field],case,int32=True)
    # Native overwrite avoids ROOT key-cycle ambiguity and leaves typed scalar
    # trees unchanged, isolating the metadata-integer guard itself.
    root=ROOT.TFile(str(config),"UPDATE")
    try:
        assert ROOT.TObjString(json.dumps(metadata)).Write("metadata",ROOT.TObject.kOverwrite)>0
    finally:
        root.Close()
    source=write_input(tmp_path/"input.root")
    result=run(native,source,config,tmp_path/"out")
    assert result.returncode==1 and "JSON integer" in result.stderr
    assert not (tmp_path/"out/cylinders.root").exists()
