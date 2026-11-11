"""LSIMUL measurements compared with freshly compiled unchanged PREAN source.

Membership is an explicit harness input: these tests do not validate CA itself.
Undefined old-shape inputs are checked only against the modern status contract.
"""
from pathlib import Path
import math
import os
import random
import shutil
import struct
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[3]
G4=ROOT/'03_mc_simulation/geant4'
ARCHIVE=ROOT/'docs/reference/fortran/prog/prean'


def run(command, **kwargs):
    p=subprocess.run([str(x) for x in command], text=True, capture_output=True,
        timeout=120, env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MACOSX_DEPLOYMENT_TARGET='15.0'),**kwargs)
    assert p.returncode==0, f'{command}\n{p.stdout}\n{p.stderr}'
    return p.stdout


@pytest.fixture(scope='module')
def binaries(tmp_path_factory):
    cpp,fort=shutil.which('c++'),shutil.which(os.environ.get('GRAAL_FORTRAN_COMPILER','gfortran'))
    if not cpp or not fort: pytest.skip('requires C++ and Fortran compilers')
    build=tmp_path_factory.mktemp('bgo-measurements')
    (build/'GRAAL_machine.h').write_text('/* Isolated source oracle. */\n')
    (build/'pilot.h').write_text('#define GRAAL_BGO_SP\n#define GRAAL_LINUX\n')
    (build/'src').mkdir()
    sources=[]
    for name in ('anabgo','anabar','calc_clust','bgo_energy','bgo_energy_correction',
                 'sigma_xy_old','sigma_xy_new','clus_flag','blockdata'):
        target=build/'src'/f'{name}.F'
        shutil.copyfile(ARCHIVE/'src'/target.name,target); sources.append(target)
    for path in (ARCHIVE/'include').glob('*.inc'): shutil.copyfile(path,build/path.name)
    modern,original=build/'check',build/'oracle'
    run([cpp,'-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-Wall','-Wextra','-Werror',
         '-I',G4/'src',G4/'tests/check_bgo_measurements.cc','-o',modern])
    run([fort,'-O0','-std=legacy','-fcheck=all','-fno-fast-math','-ffp-contract=off',
         '-ffixed-line-length-none','-cpp','-DGRAAL_BGO_SP','-DGRAAL_LINUX','-I',build,
         G4/'tests/bgo_measurements_oracle.F',*sources,'-o',original])
    return modern,original


def encode(case):
    clusters=case.get('clusters',[])
    digits=case.get('digits',[(m//100,m%100,adc) for members in clusters for m,adc in members])
    bar=case.get('bar',[])
    lines=['1', ' '.join(map(str,[len(digits),len(clusters),len(bar),case.get('error',0),
         case.get('sthres',.002),case.get('cthres',.015),2048,1,2048,.03,2048,2.e-7,case.get('abgiu',1)]))]
    lines.extend(' '.join(map(str,d)) for d in digits)
    lines.extend(' '.join(map(str,[len(c),*[m for m,_ in c]])) for c in clusters)
    lines.extend(' '.join(map(str,d)) for d in bar)
    return '\n'.join(lines)+'\n'


def compare(case,binaries):
    payload=encode(case)
    modern=run([binaries[0]],input=payload)
    assert int(modern.split()[0])==0,modern
    original=run([binaries[1]],input=payload)
    a,b=modern.splitlines(),original.splitlines()
    assert len(a)==len(b)
    assert a[0].split()==b[0].split()
    assert a[1].split()==b[1].split()
    for line1,line2 in zip(a[2:],b[2:]):
        av,bv=[float(x) for x in line1.split()],[float(x) for x in line2.split()]
        assert len(av)==len(bv)
        for x,y in zip(av,bv):
            assert math.isclose(x,y,rel_tol=8e-6,abs_tol=1e-5),(case,x,y,modern,original)


def test_guards_and_partial_shape_status(binaries):
    assert 'fixtures passed' in run([binaries[0],'--selftest'])


def test_original_boundaries_and_flags(binaries):
    cases=[{}, {'bar':[(1,0,0),(32,68,2048),(2,69,50)]},
      {'clusters':[[(801,5)]]}, {'clusters':[[(801,31)]]},
      {'clusters':[[(101,50)]],'bar':[(32,80,12)]},
      {'clusters':[[(101,50)]]}, {'clusters':[[(1501,700)]]},
      {'clusters':[[(601,801)]]},
      {'clusters':[[(201,8000)]]},
      {'clusters':[[(201,50),(301,20)]]},
      {'clusters':[[(232,50),(301,20),(401,30)]]},
      {'clusters':[[(301,50),(401,20),(603,20)]]},
      {'clusters':[[(301,100),(401,10),(603,15),(604,15)]]},
      {'clusters':[[(301,5)],[(1501,700)],[(101,50)]],'error':1},
      {'clusters':[[(301,50)]],'sthres':.0115},
      {'clusters':[[(301,100)]],'sthres':.03},
      {'clusters':[[(i*100+1,50) for i in range(2,15)]],'cthres':1},
      {'digits':[(8,1,4)],'clusters':[]},
      {'digits':[(8,1,50),(8,1,60)],'clusters':[[(801,60)]]}]
    for case in cases: compare(case,binaries)


def test_original_random_defined_cluster_domain(binaries):
    rng=random.Random(7821)
    accepted=0
    for _ in range(150):
        theta=rng.randint(2,13); phi=rng.randint(1,32)
        members=[(theta*100+phi,rng.randint(50,800)),((theta+1)*100+phi,rng.randint(10,400))]
        if rng.randrange(2): members.append(((theta-1)*100+(phi%32+1),rng.randint(5,80)))
        rng.shuffle(members)
        case={'clusters':[members],'bar':[(rng.randint(1,32),rng.randint(0,2048),rng.randint(0,2048))],
              'sthres':rng.choice([0,.001,.002,.0035,.01]),'cthres':rng.choice([.015,.1,1])}
        if any(adc<=int(2048*case['sthres']) for _,adc in members): continue
        modern=run([binaries[0]],input=encode(case))
        if int(modern.split()[0])==16: continue  # Never invoke undefined original TETA.
        compare(case,binaries); accepted+=1
    assert accepted>=80


def test_source_capacity_clipping_and_saturation(binaries):
    compare({'clusters':[[(200+j,60)] for j in range(1,33)]},binaries)
    members=[(100*i+j,20) for i in range(5,11) for j in range(13,22)][:51]
    members=[(m,1000 if m==816 else 200 if m==916 else 80 if m==614 else e) for m,e in members]
    compare({'clusters':[members]},binaries)
    for theta,limit in [(2,1100),(8,800),(14,600)]:
        for adc in (limit,limit+1): compare({'clusters':[[(theta*100+1,adc)]]},binaries)


def test_source_corrected_energy_threshold_equality(binaries):
    case={'clusters':[[(801,40)]],'cthres':0}
    lines=run([binaries[0]],input=encode(case)).splitlines()
    energy=float(lines[2].split()[4])
    case['cthres']=energy
    compare(case,binaries)
    assert run([binaries[0]],input=encode(case)).splitlines()[0].split()[1:3]==['1','0']
    bits=struct.unpack('I',struct.pack('f',energy))[0]
    case['cthres']=struct.unpack('f',struct.pack('I',bits+1))[0]
    compare(case,binaries)
    assert run([binaries[0]],input=encode(case)).splitlines()[0].split()[1:3]==['0','1']
