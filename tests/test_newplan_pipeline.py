"""Artificial boundary cases for the complete native NEW_PLAN ROOT diagnostic."""
import copy
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest
import uproot
from tests.test_digitize import SCHEMAS, STEP_INTS, STEP_DOUBLES, STEP_STRINGS, write_input, table
from mc_simulation.geant4 import newplan as launcher
from mc_simulation.geant4.legacy_response import write_newplan_config

DATA = Path(__file__).resolve().parents[1] / "docs/reference/fortran/prog/data"
PATHS = [f"/LAGR:1/PLG{1+p//2}:1/PLN{1+p//2}:{1+p%2}" for p in range(4)]
Z = [939., 949., 1339., 1349.]


def step(plane, event=0, **changes):
    row = {**dict.fromkeys(STEP_INTS,0), **dict.fromkeys(STEP_DOUBLES,0.), **dict.fromkeys(STEP_STRINGS,"")}
    row.update(run=7, event=event, track=1, track_step=1, track_weight=1., charge_e=1.,
               pre_boundary=1, path=PATHS[plane], pre_z_mm=Z[plane]-.1, material="fixture")
    row.update(changes)
    return row


def fixtures(steps=None, events=3):
    rows = [step(p) for p in range(4)] if steps is None else steps
    channels = [dict(path=PATHS[p], detector=f"plane_{1+p//2}", sensitive=8+p//2,
                     volume=f"PLN{1+p//2}", copy=1+p%2, legacy_channel=1+p%2,
                     channel_kind="chamber_plane", medium=1, material_id=1, material="fixture") for p in range(4)]
    ledger = []
    for event in range(events):
        hits = [r for r in rows if r["event"] == event]
        ledger.append(dict(run=7,event=event,total_edep_MeV=sum(r["edep_MeV"] for r in hits),
                           bgo_edep_MeV=0.,steps=len(hits),hit_steps=len(hits),aborted=0))
    return dict(channels=channels, events=ledger, detector_steps=rows, primaries=[])


@pytest.fixture
def native():
    value=os.environ.get("GRAAL_NEWPLAN_EXE")
    if not value: pytest.skip("Set GRAAL_NEWPLAN_EXE for native ROOT checks")
    assert Path(value).is_file()
    return Path(value)


@pytest.fixture
def config(tmp_path):
    target=tmp_path / "config.root"
    write_newplan_config(DATA,target)
    return target


def run(native, source, config, output):
    return subprocess.run([str(native),str(source),str(config),str(output)],capture_output=True,text=True,timeout=60)


def test_zero_deposit_entrances_order_duplicates_and_nohit_event(native, config, tmp_path):
    rows=[step(0),step(0,track=2,parent=1),step(0,pre_x_mm=20.),step(1),step(2),step(3),
          step(0,event=2,charge_e=0.),step(1,event=2,pre_boundary=0)]
    source=write_input(tmp_path / "input.root",fixtures(rows))
    digest=launcher.sha256(source)
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==0,result.stderr
    output=tmp_path / "out/tracking.root"
    events=table(output,"tracking_events")
    assert events["event"].tolist()==[0,1,2]
    assert events["crossings_u"].tolist()==[3,0,0]
    assert events["digits_u"].tolist()==[2,0,0]
    assert events["ntracks"].tolist()==[1,0,0]
    assert events["full_trigger_available"].tolist()==[0,0,0]
    cross=table(output,"plane_crossings")
    assert cross["source_step_entry"].tolist()==list(range(6))
    assert cross["pre_z_mm"][0]==pytest.approx(938.9)
    links=table(output,"crossing_digit_links")
    assert links["ordered_digit_index"].tolist()==[0,0,1,0,0,0]
    assert links["state"].tolist()==[0,1,0,0,0,0]
    assert table(output,"plane_digits")["wire"].tolist()==[161,165,161,193,193]
    assert launcher.sha256(source)==digest
    with uproot.open(output) as root:
        metadata=json.loads(str(root["metadata"]))
        assert metadata["observed_view_crossings"]==[3,1,1,1]
        assert metadata["physical_validation"] is False
        assert "not independently certify" in metadata["geometry_certification"]


@pytest.mark.parametrize("missing",range(4))
def test_single_missing_view_tracks_use_geometry_only(native,config,tmp_path,missing):
    source=write_input(tmp_path / "input.root",fixtures([step(p,pre_local_x_mm=1.e6,post_x_mm=-1.e6,pre_dir_x=-.5) for p in range(4) if p!=missing]))
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==0,result.stderr
    output=tmp_path / "out/tracking.root"
    assert table(output,"tracking_events")["ntracks"].tolist()==[1,0,0]
    assert table(output,"planar_tracks")["cl"].tolist()==[missing+1]
    assert missing not in table(output,"track_wire_links")["plane"].tolist()


def test_raw21_overflow_preserves_all_crossings_and_event(native,config,tmp_path):
    source=write_input(tmp_path / "input.root",fixtures([step(0) for _ in range(21)]))
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==0,result.stderr
    output=tmp_path / "out/tracking.root"
    events=table(output,"tracking_events")
    assert events["crossings_u"].tolist()==[21,0,0]
    assert events["kernel_status"][0]&8
    assert events["ntracks"].tolist()==[0,0,0]
    assert len(table(output,"plane_crossings")["event"])==21
    assert table(output,"crossing_digit_links")["state"].tolist()==[4]*21


@pytest.mark.parametrize("case",["unknown_path","duplicate_path","missing_plane","wrong_role","wrong_copy","schema","count","summary_count","orphan","reordered","duplicate_event","nonfinite","bad_boundary","bad_status","oldplan_z","aborted","negative","energy_mismatch"])
def test_corrupt_transport_never_publishes(native,config,tmp_path,case):
    rows=fixtures(); summary={}
    if case=="unknown_path": rows["detector_steps"][0]["path"]="/UNKNOWN:1"
    elif case=="duplicate_path": rows["channels"].append(dict(rows["channels"][0]))
    elif case=="missing_plane": rows["channels"].pop()
    elif case=="wrong_role": rows["channels"][0]["detector"]="plane_2"
    elif case=="wrong_copy": rows["channels"][0]["copy"]=2
    elif case=="schema": summary["hit_schema_version"]=1
    elif case=="count": rows["events"][0]["hit_steps"]-=1
    elif case=="summary_count": summary["detector_steps"]=99
    elif case=="orphan": rows["detector_steps"][0]["event"]=99
    elif case=="reordered":
        rows=fixtures([step(0,event=1),step(1,event=0)])
    elif case=="duplicate_event": rows["events"].append(dict(rows["events"][0]))
    elif case=="nonfinite": rows["detector_steps"][0]["pre_x_mm"]=float("nan")
    elif case=="bad_boundary": rows["detector_steps"][0]["pre_boundary"]=2
    elif case=="bad_status": rows["detector_steps"][0]["track_status"]=99
    elif case=="oldplan_z": rows["detector_steps"][0]["pre_z_mm"]=926.9
    elif case=="aborted": rows["events"][0]["aborted"]=1
    elif case=="negative": rows["detector_steps"][0]["track_weight"]=-1.
    elif case=="energy_mismatch": rows["detector_steps"][0]["edep_MeV"]=1.
    source=write_input(tmp_path / "input.root",rows,summary=summary)
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==1,result.stderr
    assert not (tmp_path / "out/tracking.root").exists()


@pytest.mark.parametrize("tree,branch",[("detector_steps","pre_x_mm"),("events","total_edep_MeV"),("primaries","px_MeV")])
def test_rejects_wrong_numeric_types_even_empty_trees(native,config,tmp_path,tree,branch):
    schemas=copy.deepcopy(SCHEMAS); schemas[tree][branch]="float32"
    source=write_input(tmp_path / "input.root",fixtures(),schemas=schemas)
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==1 and "scalar branch" in result.stderr
    assert not (tmp_path / "out/tracking.root").exists()


@pytest.mark.parametrize("case",["angle","baseline","hash","scalar_type"])
def test_rejects_config_identity_and_types(native,config,tmp_path,case):
    with uproot.open(config) as root:
        metadata=json.loads(str(root["metadata"]))
        scalars=root["scalars"].arrays(library="np")
    if case=="angle": scalars["angle_deg"][0]=45.; metadata["angle_deg"]=45.
    elif case=="baseline": metadata["baseline"][0]="GRAAL_09"
    elif case=="hash": metadata["sources"][0]["sha256"]="bad"
    else: scalars["nf1"]=scalars["nf1"].astype(np.float64)
    with uproot.recreate(config) as root:
        t=root.mktree("scalars",{k:v.dtype for k,v in scalars.items()});t.extend(scalars)
        root["metadata"]=json.dumps(metadata)
    source=write_input(tmp_path / "input.root",fixtures())
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==1,result.stderr
    assert not (tmp_path / "out/tracking.root").exists()


def test_launcher_complete_provenance_and_no_overwrite(native,tmp_path):
    source=write_input(tmp_path / "input.root",fixtures())
    output=tmp_path / "launch"
    tracking=launcher.reconstruct(source,DATA,output,native)
    with uproot.open(tracking.parent / "provenance.root") as root:
        metadata=json.loads(str(root["metadata"]))
    assert metadata["input_sha256"]==launcher.sha256(source)
    assert metadata["response_sha256"]==launcher.sha256(tracking)
    assert metadata["physical_validation"] is False
    with pytest.raises(FileExistsError): launcher.reconstruct(source,DATA,output,native)


@pytest.mark.parametrize("case",["manifest_failure","changed_input","changed_config","late_hash_change"])
def test_launcher_failure_has_no_consumable_filename(native,tmp_path,monkeypatch,case):
    source=write_input(tmp_path / "input.root",fixtures())
    if case=="manifest_failure":
        def fail(*args): raise OSError("forced provenance failure")
        monkeypatch.setattr(launcher,"_write_provenance",fail)
    elif case=="late_hash_change":
        real=launcher._write_provenance
        def changed(path,provenance):
            real(path,provenance)
            with source.open("ab") as stream: stream.write(b"changed after manifest")
        monkeypatch.setattr(launcher,"_write_provenance",changed)
    else:
        real=launcher.subprocess.run
        def changed(args,**kwargs):
            result=real(args,**kwargs)
            target=source if case=="changed_input" else Path(args[2])
            with target.open("ab") as stream: stream.write(b"changed after native digest")
            return result
        monkeypatch.setattr(launcher.subprocess,"run",changed)
    with pytest.raises((OSError,RuntimeError)): launcher.reconstruct(source,DATA,tmp_path / "launch",native)
    assert not (tmp_path / "launch/tracking/tracking.root").exists()
    assert not (tmp_path / "launch/tracking.pending/tracking.root").exists()
    assert (tmp_path / "launch/tracking.pending/tracking.invalid.root").is_file()


@pytest.mark.parametrize("plane,x,y,flag",[(2,1000.,0.,32),(0,-1000.,0.,16),(0,1000.,0.,512)])
def test_unsupported_addresses_preserve_raw_and_return_no_tracks(native,config,tmp_path,plane,x,y,flag):
    source=write_input(tmp_path / "input.root",fixtures([step(p,pre_x_mm=x if p==plane else 0.,pre_y_mm=y if p==plane else 0.) for p in range(4)]))
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==0,result.stderr
    output=tmp_path / "out/tracking.root"
    events=table(output,"tracking_events")
    assert events["kernel_status"][0]&flag
    assert events["status"][0]=="unsupported_kernel_domain"
    assert events["ntracks"].tolist()==[0,0,0]
    assert len(table(output,"plane_crossings")["event"])==4


def test_leafc_strings_are_not_native_transport_schema(native,config,tmp_path):
    source=tmp_path / "input.root"
    rows=fixtures()
    # Recreate instead of appending a second channels cycle: ROOT's name lookup
    # on a mixed PyROOT/uproot update can retain the original native-string tree.
    with uproot.recreate(source) as root:
        for name,schema in SCHEMAS.items():
            tree=root.mktree(name,schema)
            if rows[name]: tree.extend({k:[r[k] for r in rows[name]] for k in schema})
        root["summary"]=json.dumps(dict(status="diagnostic_transport_only",hit_schema_version=2,
            aborted=0,events=3,attempted_events=3,detector_steps=4))
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==1 and "requires native std::string" in result.stderr
    assert not (tmp_path / "out/tracking.root").exists()


def test_corrupt_numeric_basket_fails_cleanly(native,config,tmp_path):
    source=write_input(tmp_path / "input.root",fixtures([step(p) for _ in range(10) for p in range(4)]))
    with uproot.open(source) as root:
        key=root["detector_steps"]["pre_x_mm"].basket_key(0)
        offset,size=key.fSeekKey+key.fKeylen,key.fNbytes-key.fKeylen
        assert size<key.fObjlen
    with source.open("r+b") as stream:
        stream.seek(offset);stream.write(b"\x00"*size)
    result=run(native,source,config,tmp_path / "out")
    assert result.returncode==1 and "basket read error" in result.stderr
    assert not (tmp_path / "out/tracking.root").exists()
