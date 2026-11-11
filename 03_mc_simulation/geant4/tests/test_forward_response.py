"""Active preserved WALL/SHOW sources compiled afresh, with injected NORRAN."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import random
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]
G4 = ROOT / "03_mc_simulation/geant4"
ARCHIVE = ROOT / "docs/reference/fortran/prog"


def load_config():
    spec = importlib.util.spec_from_file_location("forward_config", G4 / "forward_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(command, **kwargs):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", MACOSX_DEPLOYMENT_TARGET="15.0")
    result = subprocess.run([str(x) for x in command], capture_output=True, text=True,
                            timeout=120, env=env, **kwargs)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result.stdout


@pytest.fixture(scope="module")
def binaries(tmp_path_factory):
    cpp, fort = shutil.which("c++"), shutil.which("gfortran")
    if not cpp or not fort:
        pytest.skip("requires c++ and gfortran")
    build = tmp_path_factory.mktemp("forward-response-oracle")
    (build / "GRAAL_machine.h").write_text("/* controlled machine */\n")
    (build / "pilot.h").write_text("#define GRAAL_26\n#define GRAAL_WALL_DEV\n#define GRAAL_SHOW_DEV\n#define GRAAL_NORRAN\n#define GRAAL_OLD_CYL\n")
    digit = build / "digit"
    digit.mkdir()
    sources, manifest = [], []
    for name in ("wall", "show", "wall_att", "blockdata"):
        source = ARCHIVE / "lagdig/src" / f"{name}.F"
        target = digit / source.name
        shutil.copyfile(source, target)
        sources.append(target)
        manifest.append(dict(path=str(source.relative_to(ROOT)), sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    for name in ("nthit", "corr", "tofwall", "russ_wall_nt", "att_wall"):
        shutil.copyfile(ARCHIVE / "lagdig/include" / f"{name}.inc", digit / f"{name}.inc")
    modern, original = build / "modern", build / "original"
    run([cpp, "-std=c++17", "-O2", "-fno-fast-math", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror",
         "-I", G4 / "src", G4 / "tests/check_forward_response.cc", "-o", modern])
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-fno-fast-math", "-ffp-contract=off", "-ffixed-line-length-none",
         "-cpp", "-DGRAAL_OLD_CYL", "-I", build, "-I", digit,
         G4 / "tests/forward_response_oracle.F", *sources, "-o", original])
    (build / "forward-response-oracle-sources.json").write_text(json.dumps(manifest, indent=2)+"\n")
    # Compile exact isolated GUSTEP branches and LAGWREV mean/time boundary.
    gustep = (ARCHIVE / "laggen/src/gustep.F").read_text()
    branch = gustep[gustep.index("    3 IF (DESTEP"):gustep.index("C ***      first cylindrical chamber")]
    finish = (ARCHIVE / "laggen/src/lagwrev.F").read_text()
    finish = finish[finish.index("          DO J = 1,LWAH"):finish.index("#if defined(GRAAL_BC448)",finish.index("          DO J = 1,LWAH"))]
    wrapper = """      SUBROUTINE COMPACT_STEP
#include "lagcoor.inc"
#include "lagmult.inc"
      INTEGER ROLE,NUMBER(1),LMEC(1),NMEC,NLEVEL
      COMMON /RAWSTEP/ DESTEP,VECT(3),TOFG,ROLE,NUMBER,NLEVEL,LMEC,NMEC
      DIMENSION YCAC(100)
      SAVE XWHCO,XWVCO,YCAC
      IF(ROLE.EQ.3) GOTO 3
      IF(ROLE.EQ.4) GOTO 4
      GOTO 5
"""+branch+"      END\n      SUBROUTINE COMPACT_FINISH\n"+'#include "lagcoor.inc"\n#include "lagmult.inc"\n'+finish+"      END\n"
    compact_source = digit / "compact.F"
    compact_source.write_text(wrapper)
    for name in ("lagcoor", "lagmult"):
        shutil.copyfile(ARCHIVE / "laggen/include" / f"{name}.inc", digit / f"{name}.inc")
    compact = build / "compact"
    run([fort, "-O0", "-std=legacy", "-fcheck=all", "-ffixed-line-length-none", "-cpp", "-DGRAAL_OLD_CYL",
         "-I", digit, G4 / "tests/forward_compaction_oracle.F", compact_source, "-o", compact])
    for name in ("laggen/src/gustep.F", "laggen/src/lagwrev.F"):
        path = ARCHIVE/name
        manifest.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    manifest.append(dict(extraction="GUSTEP labels3/4/5 through label100; LAGWREV LWAH/LWAV/LCAL mean/time loops; exact source text", mechanism=0))
    (build / "forward-response-oracle-sources.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return modern, original, compact


def encode(cases, wall=None):
    module = load_config()
    config = module.read_selected26_forward(ARCHIVE / "data")
    wall = wall or config["wall"]
    fmt = lambda seq: " ".join(format(x, ".9g") for x in seq)
    lines = [fmt([x for key in module.WALL_FIELDS for x in wall[key]]), str(len(cases))]
    for case in cases:
        groups = [case.get(key, []) for key in ("h", "v", "s")]
        lines.append(fmt([len(g) for g in groups]))
        for group in groups:
            lines += [fmt(hit) for hit in group]
        draws = case.get("draws", [0]*2000)
        lines += [str(len(draws)), fmt(draws)]
    return "\n".join(lines)+"\n"


def compare(cases, binaries, wall=None):
    payload = encode(cases, wall)
    modern = run([binaries[0]], input=payload).split()
    original = run([binaries[1]], input=payload).split()
    if modern != original:
        if len(cases)>1:
            for case in cases:
                compare([case], binaries, wall)
        pytest.fail(str(next(((i,a,b) for i,(a,b) in enumerate(zip(modern,original)) if a!=b),
                             ("token counts",len(modern),len(original))))+f" case={cases[0]}")


def test_compaction_domain_overflow_and_negative_time(binaries):
    assert "forward response fixtures passed" in run([binaries[0], "--selftest"])


def test_original_empty_thresholds_channels_edges_and_timing(binaries):
    cases = [{}]
    for ch in (1,4,5,13,14,26):
        for en in (0,.000899999,.0009,.001,.0013,.001300001,.002,.01,1,100):
            for x in (-151,-150,-110,-109.99,-10,0,10,150,151):
                cases.append(dict(h=[(ch,en,x,10e-9)],v=[(ch,en,x,10e-9)]))
    for time in (74.999e-9,75e-9,75.001e-9,94.999e-9,95e-9,95.001e-9,-100e-9):
        cases.append(dict(h=[(14,.2,0,time)],v=[(14,.2,0,time)],s=[(1,.2,0,time)]))
    for ch in (1,8,16):
        for en in (0,1e-9,1e-6,.001,.0015,.1,10):
            for x in (-151,-150,0,150,151):
                cases.append(dict(s=[(ch,en,x,10e-9)]))
    compare(cases,binaries)


def test_original_noise_draw_order_pedestal_and_negative_partial_write(binaries):
    cases = []
    rng = random.Random(4300340)
    for _ in range(160):
        n = rng.randrange(0,25)
        h = [(rng.randrange(1,27),10**rng.uniform(-4,1),rng.uniform(-160,160),rng.uniform(-50,100)*1e-9) for _ in range(n)]
        v = [(rng.randrange(1,27),10**rng.uniform(-4,1),rng.uniform(-160,160),rng.uniform(-50,100)*1e-9) for _ in range(rng.randrange(n+1))]
        s = [(rng.randrange(1,17),10**rng.uniform(-7,1),rng.uniform(-180,180),rng.uniform(-50,85)*1e-9) for _ in range(rng.randrange(40))]
        cases.append(dict(h=h,v=v,s=s,draws=[rng.gauss(0,1) for _ in range(1000)]))
    for noise in (-100,-12,0,10,100):
        cases.append(dict(h=[(1,.1,0,0),(5,.1,0,1e-9),(1,.1,30,5e-9)],
                          v=[(14,.1,0,0),(13,.1,0,0)],s=[(16,.1,0,0),(1,.0001,0,0)],draws=[noise]*1000))
    compare(cases,binaries)
    wall = load_config().read_selected26_forward(ARCHIVE / "data")["wall"]
    wall["pedestals"] = [.9]*110
    wall["tdcoffset"] = [-200]*110
    compare([dict(h=[(5,.1,0,0)],v=[(5,.1,0,0)])],binaries,wall)


def test_configuration_strict_counts_hashes_used_domain_and_root(tmp_path):
    module=load_config()
    config=module.read_selected26_forward(ARCHIVE / "data")
    assert config["sources"][0]["sha256"]=="b607d1f9111e7e0a39c6d669927a737dc4cff07d81685024cb32f02a47093288"
    assert config["sources"][1]["sha256"]=="642a605df428140aecf54026fe38303116aa6e4567f81ce0c4bd67bb11d0578e"
    assert config["simulation_rw"]["rt"]==config["shower"]["rt"]
    assert config["simulation_rw"]["ae"]==config["shower"]["ae"]
    assert config["wall"]["tdccal"][104:]==[0]*6
    data=tmp_path/"data"
    (data/"calib_wall").mkdir(parents=True)
    (data/"calib_rw").mkdir()
    shutil.copyfile(ARCHIVE/"data/calib_rw/rw_calibr_144_391.dat",data/"calib_rw/rw_calibr_144_391.dat")
    path=data/"calib_wall/calib_4300.cal"
    tokens=(ARCHIVE/"data/calib_wall/calib_4300.cal").read_text().split()
    for bad in (tokens[:-1],tokens+["0"],tokens[:110]+["0"]+tokens[111:],tokens[:111]+["NaN"]+tokens[112:]):
        path.write_text(" ".join(bad))
        with pytest.raises(ValueError): module.read_selected26_forward(data)
    path.write_text(" ".join(tokens))
    output=tmp_path/"forward.root"
    module.write_forward_config(data,output)
    import uproot
    with uproot.open(output) as root:
        assert root["wall"].num_entries==110
        assert root["shower"].num_entries==16
        assert root["simulation_rw"].num_entries==16
        assert json.loads(str(root["metadata"]))["mode"]=="selected26_forward_dev_diagnostic"
    with pytest.raises(FileExistsError): module.write_forward_config(data,output)
    assert not list(tmp_path.glob("*.partial"))


def test_original_compaction_boundaries_anchors_order_means_min_time(binaries):
    cases = []
    for role in (3,4,5):
        limit = 10 if role==5 else 5
        for distance in (limit-.0001,limit,limit+.0001):
            for time in (9.999e-9,10e-9,10.001e-9,2e-6):
                cases.append((role,[(1,.001,0,0),(1,.002,distance,time),(2,.003,0,0),(1,.004,0,time)]))
        cases.append((role,[(1,0,0,0),(1,1e-9,0,0),(1,1.00001e-9,0,2e-6)]))
    rng=random.Random(3404300)
    for role in (3,4,5):
        for _ in range(50):
            cases.append((role,[(rng.randrange(1,4),rng.uniform(1e-9,.1),rng.randrange(-2,3)*4.9,rng.randrange(0,6)*4e-9)
                                for _ in range(rng.randrange(1,70))]))
    fmt=lambda xs:" ".join(format(x,".9g") for x in xs)
    lines=[str(len(cases))]
    for role,steps in cases:
        lines.append(f"{role} {len(steps)}")
        lines += [fmt(step) for step in steps]
    payload="\n".join(lines)+"\n"
    modern=run([binaries[0],"--compact"],input=payload).split()
    original=run([binaries[2]],input=payload).split()
    assert modern==original, next(((i,a,b) for i,(a,b) in enumerate(zip(modern,original)) if a!=b),"different counts")


def test_original_exact_end_thresholds_saturation_partial_second_end_and_capacity100(binaries):
    wall=load_config().read_selected26_forward(ARCHIVE/"data")["wall"]
    for key in ("tdccal","gaincards","gainpms"):
        wall[key]=[1]*110
    for key in ("pedestals","timewalk","tdcoffset"):
        wall[key]=[0]*110
    cases=[]
    for energy in (.009999999,.01,.010000001):
        cases.append(dict(h=[(5,energy,151,10e-9)],v=[(5,energy,151,10e-9)]))
    cases += [dict(h=[(5,.1,0,0)],v=[(14,.1,0,0)]),
              dict(h=[(14,.1,0,0)],v=[(5,.1,0,0)]),
              dict(h=[(5,10,0,95e-9)],v=[(5,10,0,95e-9)]),
              dict(h=[(5,.01,151,10e-9)]*100,v=[(5,.01,151,10e-9)]*100,s=[(1,.1,0,10e-9)]*100)]
    compare(cases,binaries,wall)
    wall["pedestals"]=[.9]*110
    compare([dict(h=[(5,.0109,151,10e-9)],v=[(5,.0109,151,10e-9)])],binaries,wall)
    wall["tdcoffset"][83]=-200  # H5 right (1-based channel83+1)
    compare([dict(h=[(5,.1,0,10e-9)])],binaries,wall)
    wall["tdcoffset"]=[10000]*110
    compare([dict(h=[(5,.1,0,10e-9)],v=[(5,.1,0,10e-9)])],binaries,wall)
