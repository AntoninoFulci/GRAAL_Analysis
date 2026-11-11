"""Recovered original C is compiled untouched, with controlled COMMON/rand."""
from pathlib import Path
import hashlib
import importlib.util
import json
import math
import os
import random
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[3]
G4=ROOT/'03_mc_simulation/geant4'
ARCHIVE=ROOT/'docs/reference/fortran/lib_cluster_c'
COUNTS={"events":0,"draws":0}

def run(args,**kwargs):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MACOSX_DEPLOYMENT_TARGET='15.0'),**kwargs)
    assert p.returncode==0,p.stderr+'\n'+p.stdout
    return p.stdout

@pytest.fixture(scope='module',autouse=True)
def evidence(tmp_path_factory):
    output = tmp_path_factory.mktemp('bgo-cellular-evidence')
    yield
    (output/'bgo-cellular-oracle-counts.json').write_text(json.dumps(COUNTS,indent=2)+'\n')

@pytest.fixture(scope='module')
def bins(tmp_path_factory):
    d=tmp_path_factory.mktemp('bgo-cellular-oracle');src=d/'src';src.mkdir()
    files=[]
    for p in sorted((ARCHIVE/'src').glob('*.c')):
        q=src/p.name;shutil.copyfile(p,q);assert q.read_bytes()==p.read_bytes();files.append(q)
    modern=d/'modern';original=d/'original'
    common=['-fno-fast-math','-ffp-contract=off','-fsanitize=address,undefined','-fno-sanitize-recover=all']
    run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror',*common,'-I',G4/'src',G4/'tests/check_bgo_cellular.cc','-o',modern])
    run(['cc','-std=gnu99','-O0','-fcommon',*common,'-Drand=oracle_rand','-I',ARCHIVE/'include','-I',ROOT/'docs/reference/fortran/prog/include',G4/'tests/bgo_cellular_oracle.c',*files,'-lm','-o',original])
    return modern,original

@pytest.fixture(scope='module')
def tables():
    spec=importlib.util.spec_from_file_location('forward_config',G4/'forward_config.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    source=(ROOT/'docs/reference/fortran/prog/prean/src/blockdata.F').read_text()
    return dict(theta=m._table(source,'TET',15),phi=m._table(source,'PHI',32),volume=m._table(source,'VOL',15))

def grid(hits):
    out=[0.0]*480
    for theta,phi,energy in hits:out[theta-1+15*(phi-1)]=energy
    return out

def encode(cases,tables,rcnt=.2,tde=8):
    fmt=lambda v:' '.join(str(x) if isinstance(x,int) else format(x,'.9g') for x in v)
    lines=[fmt([len(cases),rcnt,tde]),fmt(tables['theta']),fmt(tables['phi']),fmt(tables['volume'])]
    for c in cases:
        g=c.get('grid',grid(c.get('hits',[])));active=sum(x>0 for x in g)
        values=c.get('draws',[0]*active)
        lines+=[fmt(g),str(len(values)),fmt(values)]
    return '\n'.join(lines)+'\n'

def compare(cases,bins,tables,**config):
    text=encode(cases,tables,**config)
    modern=run([bins[0]],input=text)
    original=run([bins[1]],input=text)
    original='\n'.join(line for line in original.splitlines() if line.startswith(('O ','C ')))+'\n'
    assert modern==original,(modern[:3000],original[:3000],cases[:3])
    COUNTS['events']+=len(cases)
    COUNTS['draws']+=sum(int(line.split()[3]) for line in modern.splitlines() if line.startswith('O '))
    return modern

def test_empty_single_scan_order_and_repeated_calls(bins,tables):
    single=dict(hits=[(8,15,.02)])
    cases=[{},single,single,{},dict(hits=[(1,1,.01),(15,32,.02)]),dict(hits=[(1,1,-.1),(2,2,.02)])]
    text=compare(cases,bins,tables)
    assert 'O 0 3 0 0' in text and 'C 1 815' in text
    assert 'CA public domain and repeat fixtures passed' in run([bins[0],'--selftest'],input=encode([],tables))

def test_neighbors_seams_theta_edges_equal_energy_and_stream_endpoints(bins,tables):
    cases=[]
    for t in (1,2,8,14,15):
        for p in (1,2,16,31,32):
            neighbors=[(t,p,.02),(min(t+1,15),1 if p==32 else p+1,.02)]
            # No duplicate coordinates, including theta15, still distinct phi.
            for values in ([0,0],[2147483647,0],[0,2147483647],[2147483647]*2):cases.append(dict(hits=neighbors,draws=values))
    compare(cases,bins,tables)

def test_peaks_bridges_contact_and_distance_boundaries(bins,tables):
    cases=[]
    for ratio in (.1,.199999,.2,.200001,.5,1):
        for split in (1,2,3,8,16,31):
            cases.append(dict(hits=[(8,1,.1),(8,split+1,.1*ratio)]))
            cases.append(dict(hits=[(8,1,.1),(8,2,.001),(8,3,.1*ratio)]))
    for rcnt in (0,.199999,.2,.200001,1):
        compare(cases,bins,tables,rcnt=rcnt,tde=8)
    for tde in (0,.1,1,8,100):compare(cases,bins,tables,rcnt=.2,tde=tde)

def test_all480_and_many_maxima_source_ordering(bins,tables):
    rng=random.Random(480)
    # Full equal plateaus exercise all480 initial maxima and later merge order.
    cases=[dict(grid=[.001]*480),dict(grid=[.001]*480,draws=[rng.randrange(2147483648) for _ in range(480)]),dict(hits=[(t,p,.001*(1+(t+p)%3)) for t in range(1,16,2) for p in range(1,33,2)])]
    compare(cases,bins,tables,rcnt=.2,tde=8)

def test_deterministic_random_measured_energy_maps(bins,tables):
    rng=random.Random(20261109);cases=[]
    for _ in range(120):
        indices=rng.sample(range(480),rng.randrange(1,81));g=[0.]*480
        for i in indices:g[i]=rng.choice((.001,.002,.01,.02,.1)) if rng.random()<.5 else rng.uniform(.001,.1)
        cases.append(dict(grid=g,draws=[rng.randrange(2147483648) for _ in indices]))
    compare(cases,bins,tables)

def test_exact_contact_and_distance_threshold_equalities(bins,tables):
    import struct
    f32=lambda x:struct.unpack('f',struct.pack('f',x))[0]
    def adjacent(x,delta):
        bits=struct.unpack('I',struct.pack('f',x))[0]
        return struct.unpack('f',struct.pack('I',bits+delta))[0]
    # The bridge joins the larger peak: fever=.625 vs .25. Its contact
    # threshold product at source-float RCNT=.4 is exactly .25.
    contact=[dict(hits=[(8,1,.5),(8,2,.125),(8,3,.25)])]
    threshold=f32(.4)
    for rcnt,count in ((adjacent(threshold,-1),2),(threshold,1),(adjacent(threshold,1),1)):
        out=compare(contact,bins,tables,rcnt=rcnt,tde=1e30)
        assert out.splitlines()[0]==f'O 0 0 3 {count}'
    # Two isolated crystals: distance=22.5/360=.0625 exactly, source talfa
    # is float32((.5-.25)/((.5+.25)*.0625)); strict> means equality separates.
    distant=[dict(hits=[(8,1,.5),(8,3,.25)])]
    threshold=f32(.25/(.75*.0625))
    for tde,count in ((adjacent(threshold,-1),1),(threshold,2),(adjacent(threshold,1),2)):
        out=compare(distant,bins,tables,rcnt=.2,tde=tde)
        assert out.splitlines()[0]==f'O 0 0 2 {count}'

def test_source_seam_shift_and_contact_scan_topologies(bins,tables):
    cases=[]
    for energy in (.05,.2,.8):
        cases.append(dict(hits=[(5,32,.5),(5,1,.1),(10,16,energy),(10,17,.01)]))
        cases.append(dict(hits=[(8,1,.5),(8,2,.1),(9,4,energy),(10,3,.01),(10,4,.02)]))
    compare(cases,bins,tables)
