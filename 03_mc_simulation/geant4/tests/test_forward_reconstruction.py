"""Independent unchanged-source oracles for active forward reconstruction."""
from pathlib import Path
import importlib.util
import json
from collections import Counter
import math
import os
import random
import shutil
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[3]
G4=ROOT/'03_mc_simulation/geant4'
COMPARISONS=Counter()
UNSUPPORTED=Counter()

@pytest.fixture(scope='module',autouse=True)
def evidence(tmp_path_factory):
    output = tmp_path_factory.mktemp('forward-reconstruction-evidence')
    yield
    (output/'forward-reconstruction-oracle-counts.json').write_text(json.dumps(dict(original_source_comparisons=dict(COMPARISONS),guarded_random_domains=dict(UNSUPPORTED)),indent=2)+'\n')

def module(name):
    spec=importlib.util.spec_from_file_location(name,G4/('tests/generate_forward_kernels.py' if name=='generator' else 'forward_config.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def run(args,**kw):
    p=subprocess.run(list(map(str,args)),capture_output=True,text=True,timeout=120,env=dict(os.environ,MACOSX_DEPLOYMENT_TARGET='15.0',PYTHONDONTWRITEBYTECODE='1'),**kw)
    assert p.returncode==0,p.stderr+'\n'+p.stdout
    return p.stdout

@pytest.fixture(scope='module')
def bins(tmp_path_factory):
    d=tmp_path_factory.mktemp('forward-reconstruction-oracle');src=module('generator').prepare(d)
    cpp=d/'cpp';f=d/'fortran'
    run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined,address','-fno-sanitize-recover=all','-fno-fast-math','-ffp-contract=off','-I',G4/'src',G4/'tests/check_forward_reconstruction.cc','-o',cpp])
    run(['gfortran','-O0','-std=legacy','-fcheck=all','-finit-real=snan','-finit-integer=-1000000000','-fno-fast-math','-ffp-contract=off','-ffixed-line-length-none','-cpp','-I',d,'-I',src,G4/'tests/forward_reconstruction_oracle.F',*[src/f'{n}.F' for n in module('generator').NAMES],'-o',f])
    return cpp,f

@pytest.fixture(scope='module')
def cfg():return module('config').read_selected26_forward(ROOT/'docs/reference/fortran/prog/data')

def payload(case,cfg):
    fmt=lambda xs:' '.join(format(x,'.9g') for x in xs)
    wall=cfg['wall'];rw=cfg['simulation_rw'];a=cfg['attenuation']
    lines=[fmt([v for key in module('config').WALL_FIELDS for v in wall[key]]),fmt(rw['rt']+rw['rb']+[rw['ay']]+rw['by']+rw['bt']+rw['ae']),fmt(a['attn']+a['atts']+a['atth']),fmt(case.get('config',[94,134.4,300,4300,0,1]))]
    groups=[case.get(key,[]) for key in ('h','v','s','p')]
    lines.append(fmt([case.get('mode',4)]+list(map(len,groups))))
    for group in groups:lines += list(map(fmt,group))
    if case.get('mode')==5:lines.append(fmt(case['double']))
    if case.get('mode')==3:
        lines.append(fmt([len(case.get('wall',[])),len(case.get('rw',[]))]))
        lines+=list(map(fmt,case.get('wall',[])+case.get('rw',[])))
    return '\n'.join(lines)+'\n'

def compare(case,bins,cfg):
    p=payload(case,cfg);modern=run([bins[0]],input=p);old=run([bins[1]],input=p)
    a,b=modern.split(),old.split();assert len(a)==len(b),(case,modern,old)
    for i,(x,y) in enumerate(zip(a,b)):
        try: fx,fy=float(x),float(y)
        except ValueError:assert x==y,(i,case,modern,old);continue
        assert math.isfinite(fx) and math.isfinite(fy),(case,modern,old)
        if '.' not in x and 'e' not in x.lower():assert x==y,(i,case,modern,old)
        else:assert fx==pytest.approx(fy,rel=3e-6,abs=3e-5 if abs(fy)>1e-5 else 1e-13),(i,case,modern,old)
    COMPARISONS[str(case.get('mode',4))]+=1
    return modern

def wall_digit(c,ch,pos=0,time=20,energy=10,plane=0):
    w=c['wall'];idx=[ch+51,ch+77] if plane==0 else [ch-1,ch+25]
    t=[time+9.375-pos/16,time+9.375+pos/16]
    if plane==0 and ch<=4:t[1]-=2.5
    adc=[int(energy/w['gainpms'][i]/w['gaincards'][i]+w['pedestals'][i]) for i in idx]
    ene=[(adc[j]-w['pedestals'][i])*w['gaincards'][i] for j,i in enumerate(idx)]
    tdc=[int((t[j]+w['timewalk'][i]/math.sqrt(ene[j])+w['tdcoffset'][i])/w['tdccal'][i]) for j,i in enumerate(idx)]
    return [ch,*adc,*tdc]

def shower_digit(c,ch,y=0,time=15,energy=30):
    r=c['simulation_rw'];i=ch-1
    # TT-TB=(y-BY)/AY; mean=BT-time before length correction.
    diff=(y-r['by'][i])/r['ay'];mean=r['bt'][i]-time
    return [ch,int(energy/r['ae'][i]),int(energy/r['ae'][i]),max(0,int((mean+.5*diff)/r['rt'][i])),max(0,int((mean-.5*diff)/r['rb'][i]))]

def pc(x=20,y=10):return [x*94/134.4,y*94/134.4,x,y,1]
def wc(x=45,y=22,tof=20,de=10,association=0):return [x,y,tof,de,tof,de,tof,de,association]
def rw(x=50,y=25,t=15e-9,e=.03,phi=20):return [x,y,t,e,phi]

def test_empty_all_components_and_chain(bins,cfg):
    for mode in (1,2,3,4):compare(dict(mode=mode),bins,cfg)

def test_wall_channels_short_hole_edges_and_source_multiplicity(bins,cfg):
    for ch in (1,4,5,12,13,14,15,26):
        for pos in (-145,-10,0,10,145):
            compare(dict(mode=1,h=[wall_digit(cfg,ch,pos)],v=[wall_digit(cfg,ch,pos,plane=1)]),bins,cfg)
            compare(dict(mode=1,h=[wall_digit(cfg,ch,pos)]),bins,cfg)
    for plane in ('h','v'):
        compare(dict(mode=1,**{plane:[wall_digit(cfg,i,plane=plane=='v') for i in (2,6,10,20)]}),bins,cfg)

def test_wall_adjacency_double_bar_search(bins,cfg):
    # Nonadjacent/adjacent three-bar patterns, time separation, both wall axes.
    for hs,vs in (([12,13],[13]),([13],[12,13]),([9,10,11],[10,11]),([8,15],[8,15]),([1,2],[3,4]),([12,13,14],[12,13,14])):
        for time in (0,1.9,2.1,6):
            h=[wall_digit(cfg,ch,(vs[0]-13.5)*11.54,20+(i%2)*time) for i,ch in enumerate(hs)]
            v=[wall_digit(cfg,ch,(hs[0]-13.5)*11.54,20+(i%2)*time,plane=1) for i,ch in enumerate(vs)]
            compare(dict(mode=1,h=h,v=v),bins,cfg)

def test_shower_neighbor_time_separation_and_unrecognized(bins,cfg):
    for channels in ((1,),(8,),(16,),(7,8),(7,8,9),(7,8,9,10),(14,15,16)):
        for dt in (0,1.9,2,2.1,10):
            for dy in (0,39.5,40.5):
                compare(dict(mode=2,s=[shower_digit(cfg,ch,i*dy,15+i*dt) for i,ch in enumerate(channels)]),bins,cfg)
    for raw in ([1,0,0,0,0],[16,10,10,9,500],[8,100,100,0,0]):compare(dict(mode=2,s=[raw]),bins,cfg)

def test_association_masks_boundaries_ties_mapping_and_units(bins,cfg):
    for mask in range(1,8):
        c=dict(mode=3,p=[pc()] if mask&4 else [],wall=[wc()] if mask&2 else [],rw=[rw()] if mask&1 else [])
        out=compare(c,bins,cfg);assert f'AM {mask} ' in out
    for delta in (4.999,5,5.001):
        p=pc();p[2]+=delta;compare(dict(mode=3,p=[p],wall=[wc()],rw=[rw()]),bins,cfg)
    for delta in (1.49999,1.5,1.50001):
        compare(dict(mode=3,p=[pc(0,0)],wall=[wc(11.54*delta,0)]),bins,cfg)
        compare(dict(mode=3,p=[pc(0,0)],rw=[rw(19.22*delta,0)]),bins,cfg)
    for info in (-2,0,1,2,3,4,10):compare(dict(mode=3,p=[pc(),pc()],wall=[wc(association=info),wc()],rw=[rw(),rw()]),bins,cfg)
    compare(dict(mode=3,p=[pc(0,0),pc(50,30)],wall=[wc(-100,-100)],rw=[rw(140,140),rw(-100,-100)]),bins,cfg)
    compare(dict(mode=3,p=[pc(-20,10)],wall=[wc(-45,22)],rw=[rw(50,25)],config=[94,134.4,300,4300,0,0]),bins,cfg)

def test_full_chain_and_russwall_planar_classifier(bins,cfg):
    for sim in (0,1):
        for ch in (4,8,13,16):
            for rf in (-1,0,1):
                compare(dict(h=[wall_digit(cfg,14,0)],v=[wall_digit(cfg,14,0,plane=1)],s=[shower_digit(cfg,ch)],p=[pc(10,10)],config=[94,134.4,300,4300,rf,sim]),bins,cfg)

def test_undefined_source_paths_are_not_oracle_goldens(bins,cfg):
    cases=[dict(mode=1,h=[wall_digit(cfg,12),wall_digit(cfg,13)]),dict(mode=2,v=[wall_digit(cfg,13,plane=1)],s=[shower_digit(cfg,8)],p=[pc()]),dict(mode=2,h=[wall_digit(cfg,13)],s=[shower_digit(cfg,8)],p=[pc()],config=[94,134.4,300,1000,0,1])]
    for case in cases:assert 'UNSUPPORTED' in run([bins[0]],input=payload(case,cfg))

def test_config_explicit_run_geometry_and_atomic_tables(tmp_path):
    spec=importlib.util.spec_from_file_location('reconstruction_config',G4/'forward_reconstruction_config.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    data=ROOT/'docs/reference/fortran/prog/data'
    with pytest.raises(TypeError):m.read_selected26_forward_reconstruction(data)
    for bad in (True,-1,65536,4300.0):
        with pytest.raises(ValueError):m.read_selected26_forward_reconstruction(data,source_run=bad)
    c=m.read_selected26_forward_reconstruction(data,source_run=1321)
    assert c['reconstruction']==dict(zp1_cm=pytest.approx(94.4),zp2_cm=pytest.approx(134.4),zp3_cm=pytest.approx(301.53),source_run=1321,rf_bunch=0,simulation=True)
    assert c['wall']==module('config').read_selected26_forward(data)['wall']
    target=tmp_path/'config.root';m.write_forward_reconstruction_config(data,target,source_run=1321)
    import uproot
    with uproot.open(target) as f:
        assert f['reconstruction'].num_entries==1
        assert f['reconstruction']['source_run'].array(library='np')[0]==1321
        assert f['wall'].num_entries==110 and f['simulation_rw'].num_entries==16
    with pytest.raises(FileExistsError):m.write_forward_reconstruction_config(data,target,source_run=4300)
    assert not list(tmp_path.glob('*.partial'))

def test_source_run1321_only_rejects_traversed_undefined_alignment(bins,cfg):
    for case in (dict(mode=2),dict(mode=2,s=[shower_digit(cfg,8)]),dict(mode=2,s=[[8,0,0,0,0]],p=[pc()],h=[wall_digit(cfg,13)])):
        case['config']=[94.4,134.4,301.53,1321,0,1];compare(case,bins,cfg)
    case=dict(mode=2,s=[shower_digit(cfg,8)],p=[pc()],h=[wall_digit(cfg,13)],config=[94.4,134.4,301.53,1321,0,1])
    assert 'RUSSWALL.alignment' in run([bins[0]],input=payload(case,cfg))

def test_association_first_tie_and_no_endpoint_reuse(bins,cfg):
    c=dict(mode=3,p=[pc(),pc()],wall=[wc(),wc()],rw=[rw(),rw()])
    text=compare(c,bins,cfg)
    assert 'AM 7 1 1 1\nAM 7 2 2 2' in text
    c=dict(mode=3,p=[pc(0,0)],wall=[wc(11.54*1.5,0)])
    text=compare(c,bins,cfg);assert 'AM 6' not in text
    for delta,accepted in ((4.999,True),(5,False),(5.001,False)):
        text=compare(dict(mode=3,p=[[0,0,delta,0,1]]),bins,cfg)
        assert ('AM 4' in text)==accepted


def test_double_bar_all_four_source_branches(bins,cfg):
    for opt in (1,2):
        for associated in (0,1):
            text=compare(dict(mode=5,double=[opt,associated]),bins,cfg)
            assert f'D 0 2' in text
            code=opt if associated else 3 if opt==1 else 4
            assert all(int(line.split()[-1])==code for line in text.splitlines() if line.startswith('DC'))

def test_double_bar_digit_to_cluster_source_fixtures(bins,cfg):
    cases=[
        dict(mode=1,h=[[10,39,37,1004,839],[12,62,54,1061,711]],v=[[8,88,93,792,723]]),
        dict(mode=1,h=[[11,17,30,1017,680],[15,21,28,950,881]],v=[[8,64,64,778,764]]),
        dict(mode=1,h=[[8,104,109,867,777]],v=[[10,56,81,1014,852],[12,58,73,968,775]])]
    for case,code in zip(cases,(1,3,2)):
        text=compare(case,bins,cfg)
        assert code in [int(line.split()[-1]) for line in text.splitlines() if line.startswith('WC')]


def test_public_status_capacity_availability_and_index_domain(bins,cfg):
    assert 'public boundary fixtures passed' in run([bins[0]],input=payload(dict(mode=6),cfg))

def test_deterministic_random_defined_source_oracles(bins,cfg):
    rng=random.Random(261109)
    for _ in range(100):
        hs=rng.sample(range(1,27),rng.randint(1,3));vs=rng.sample(range(1,27),rng.randint(1,3))
        case=dict(mode=1,h=[wall_digit(cfg,ch,rng.uniform(-145,145),rng.uniform(10,60),rng.uniform(2,30)) for ch in hs],v=[wall_digit(cfg,ch,rng.uniform(-145,145),rng.uniform(10,60),rng.uniform(2,30),plane=1) for ch in vs])
        modern=run([bins[0]],input=payload(case,cfg))
        # A source out-of-bounds branch is an explicit unsupported case, never
        # an original oracle golden. Most generated cases stay defined.
        if 'UNSUPPORTED' not in modern:compare(case,bins,cfg)
        else:UNSUPPORTED[modern.strip()]+=1
    for _ in range(60):
        channels=rng.sample(range(1,17),rng.randint(1,16))
        compare(dict(mode=2,s=[shower_digit(cfg,ch,rng.uniform(-165,165),rng.uniform(8,65),rng.uniform(1,100)) for ch in channels]),bins,cfg)
    for _ in range(60):
        compare(dict(mode=3,p=[pc(rng.uniform(-50,50),rng.uniform(-50,50)) for _ in range(rng.randint(0,6))],wall=[wc(rng.uniform(-140,140),rng.uniform(-140,140)) for _ in range(rng.randint(0,3))],rw=[rw(rng.uniform(-150,150),rng.uniform(-150,150)) for _ in range(rng.randint(0,8))]),bins,cfg)


def test_source_run_short_bar_and_data_alignment_profiles(bins,cfg):
    for run in (0,340,391,392,832,2242,4300):
        compare(dict(mode=1,h=[wall_digit(cfg,1)],v=[wall_digit(cfg,1,plane=1)],config=[94.4,134.4,301.53,run,0,1]),bins,cfg)
    for run in (832,834,1321,2241,2242):
        compare(dict(mode=2,h=[wall_digit(cfg,14)],v=[wall_digit(cfg,14,plane=1)],s=[shower_digit(cfg,8)],p=[pc(10,10)],config=[94.4,134.4,301.53,run,0,0]),bins,cfg)
