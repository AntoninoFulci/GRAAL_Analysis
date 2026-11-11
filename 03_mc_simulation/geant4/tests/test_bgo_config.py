"""Explicit initialization, independent database axes and typed publication."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil
import struct
import pytest

ROOT=Path(__file__).resolve().parents[3]
SPEC=importlib.util.spec_from_file_location('bgo_config',ROOT/'03_mc_simulation/geant4/bgo_config.py')
CONFIG=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CONFIG)
DATA=ROOT/'docs/reference/fortran/prog/data'


@pytest.fixture
def environment_evidence(tmp_path):
    path=tmp_path/'environment.txt'
    path.write_text('echo $BGO_SOFT_THRES\n0.002\n'
                    'echo $CLUS_SOFT_THRES\n0.015\n'
                    'export BGO_SOFT_THRES=0.002\nexport CLUS_SOFT_THRES=0.015\n')
    return path


def settings():
    return dict(crystal_threshold=.002,cluster_threshold=.015,barrel_energy_threshold_mev=1,
                ca_rcnt=.5,ca_tde=.1,xba1=[0]*32,initialization_claim='Synthetic initialized unit fixture; not historical settings')


def f32(value): return struct.unpack('f',struct.pack('f',value))[0]


def test_required_config_and_source_scales():
    with pytest.raises(TypeError): CONFIG.read_bgo_config(DATA)
    c=CONFIG.read_bgo_config(DATA,**settings())
    assert c['scalars']['barrel_adc_fullscale_gev']==f32(.02294)
    assert c['scalars']['bgo_adc_fullscale_gev']==f32(1.2901)
    assert c['scalars']['barrel_tdc_fullscale_seconds']==f32(116.3e-9)
    assert len(c['sources'])>30
    assert all(Path(v['path']).is_absolute() for v in c['sources'])
    assert c['theta']['theta']==[f32(v) for v in [28,34.5,41.75,50.5,60.5,70.5,80.33333,90,99.66667,109.5,119.5,129.5,138.25,145.5,152]]
    assert c['corrections']['a'][:3]==[f32(v) for v in [.1865306,.5437917,2.028834]]
    assert c['corrections']['b'][-1]==f32(1.064629)
    assert c['simulation'] is True and not c['physics_validation']
    source_xba=CONFIG.source_selected26_xba1(DATA)
    assert len(source_xba)==32 and source_xba[0]==f32(.32861251)
    assert source_xba[22]==f32(.005)


@pytest.mark.parametrize('key,value',[('crystal_threshold',float('nan')),('cluster_threshold',-1),
    ('barrel_energy_threshold_mev',float('inf')),('ca_rcnt',float('nan')),('ca_tde',float('inf')),('xba1',[0]*31),
    ('xba1',[0]*31+[float('nan')]),('initialization_claim',''),('enable_sp',1)])
def test_reject_invalid_initialized_state(key,value):
    values=settings();values[key]=value
    with pytest.raises(ValueError): CONFIG.read_bgo_config(DATA,**values)


def test_reject_database_record_change(tmp_path):
    (tmp_path/'base').mkdir()
    path=tmp_path/'base/data09.base'
    shutil.copyfile(DATA/'base/data09.base',path)
    path.write_text(path.read_text().replace('!SCDEB','!WRONG'))
    with pytest.raises(ValueError,match='SCDEB'): CONFIG.read_bgo_config(tmp_path,**settings())


def test_typed_atomic_publication(tmp_path):
    uproot=pytest.importorskip('uproot')
    path=tmp_path/'fixture.root'
    c=CONFIG.write_bgo_config(DATA,path,**settings())
    with uproot.open(path) as root:
        assert root['scalars']['crystal_threshold'].typename=='float'
        assert root['scalars']['enable_sp'].typename=='bool'
        assert root['theta']['index'].typename=='int32_t'
        assert root['phi']['xba1'].array(library='np').tolist()==[0]*32
        assert json.loads(str(root['metadata']))==c
    with pytest.raises(FileExistsError): CONFIG.write_bgo_config(DATA,path,**settings())
    assert not list(tmp_path.glob('*.partial'))


def test_modern_profile_uses_database_threshold_and_explicit_lsimul_policy(environment_evidence):
    c=CONFIG.read_modern_prean_profile(DATA,environment_evidence=environment_evidence)
    s=c['scalars']; policy=c['modern_initialization']
    assert s['crystal_threshold']==f32(.002) and s['cluster_threshold']==f32(.015)
    assert s['barrel_energy_threshold_mev']==f32(1)
    assert s['ca_rcnt']==pytest.approx(.17,abs=2e-8) and s['ca_tde']==8
    assert policy['ca']['threshold_gev']==f32(.0022)
    assert policy['ca']['threshold_symbol']=='THRES'
    assert policy['ca']['tables']['rcnt']==[f32(v) for v in [.16,.19,.21,.23,.28,.30]]
    assert policy['ca']['tables']['tde']==[8,8,8,7,7,6]
    assert policy['ca']['units']['tde']=='dimensionless'
    assert policy['historical_runtime_reproduction'] is False
    assert policy['abgiu']['assigned_for_lsimul'] is True
    assert policy['abgiu']['GRAAL_ETA_PI0GG'] is False
    assert s['barrel_adc_fullscale_gev']==f32(.02294)  # legacy09, not selected26 .02306
    assert c['phi']['xba1']==CONFIG.source_selected26_xba1(DATA)
    paths={v['path']:v['sha256'] for v in c['sources']}
    for path in (DATA/'base/data26.base',environment_evidence,
                 ROOT/'docs/reference/fortran/prean/src/init_ca.F',
                 ROOT/'docs/reference/fortran/prean/src/constan.F'):
        assert paths[str(path.resolve())]==hashlib.sha256(path.read_bytes()).hexdigest()


def test_ca_interpolation_knots_and_threshold_distinction():
    tables=CONFIG._read_ca_tables(ROOT/'docs/reference/fortran/prean/src/init_ca.F')
    for x,rcnt,tde in zip(tables['sog_gev'],tables['rcnt'],tables['tde']):
        assert CONFIG._linear_binary32(x,tables['sog_gev'],tables['rcnt'])==rcnt
        assert CONFIG._linear_binary32(x,tables['sog_gev'],tables['tde'])==tde
    assert CONFIG._linear_binary32(.002,tables['sog_gev'],tables['rcnt'])==pytest.approx(.165,abs=2e-8)
    assert CONFIG._linear_binary32(.0125,tables['sog_gev'],tables['tde'])==f32(6.5)
    for threshold in (.0017,.0151,float('nan')):
        with pytest.raises(ValueError):
            CONFIG._linear_binary32(threshold,tables['sog_gev'],tables['rcnt'])


@pytest.mark.parametrize('old,new',[
    ('0.0018,0.003','0.003,0.0018'), ('0.0018,0.003','0.0018,0.0018'),
    ('0.16,0.19','0.16,nan'), ('0.16,0.19','0.16'),
    ('      DATA RCNT1 /0.16','C     DATA RCNT1 /0.16'),
    ('      DATA RCNT1 /0.16','      DATA RCNT1 /0.1,0.2,0.3,0.4,0.5,0.6/\n      DATA RCNT1 /0.16'),
    ('THRES,1','STHRES,1'),
])
def test_reject_invalid_ca_source(tmp_path,old,new):
    path=tmp_path/'init_ca.F'
    path.write_text((ROOT/'docs/reference/fortran/prean/src/init_ca.F').read_text().replace(old,new))
    with pytest.raises(ValueError): CONFIG._read_ca_tables(path)


@pytest.mark.parametrize('old,new',[
    ('!THRES','!STHRES'), (' 2.2E-3         ',' 1.0E-3         '),
])
def test_modern_rejects_invalid_threshold_source(tmp_path,environment_evidence,old,new):
    shutil.copytree(DATA/'base',tmp_path/'base')
    path=tmp_path/'base/data26.base'
    path.write_text(path.read_text().replace(old,new))
    with pytest.raises(ValueError):
        CONFIG.read_modern_prean_profile(tmp_path,environment_evidence=environment_evidence)


@pytest.mark.parametrize('text',[
    'export BGO_SOFT_THRES=0.002\n',
    'export BGO_SOFT_THRES=0.003\nexport CLUS_SOFT_THRES=0.015\n',
    'export BGO_SOFT_THRES=0.002\nexport CLUS_SOFT_THRES=0.015\nexport CLUS_SOFT_THRES=0.020\n',
    'echo $BGO_SOFT_THRES\n0.003\nexport BGO_SOFT_THRES=0.002\nexport CLUS_SOFT_THRES=0.015\n',
])
def test_modern_rejects_missing_or_inconsistent_environment(environment_evidence,text):
    environment_evidence.write_text(text)
    with pytest.raises(ValueError):
        CONFIG.read_modern_prean_profile(DATA,environment_evidence=environment_evidence)


def test_modern_profile_root_metadata_and_no_overwrite(tmp_path,environment_evidence):
    uproot=pytest.importorskip('uproot')
    output=tmp_path/'modern.root'
    c=CONFIG.write_modern_prean_profile(DATA,output,environment_evidence=environment_evidence)
    with uproot.open(output) as root:
        assert json.loads(str(root['metadata']))==c
        assert root['scalars']['ca_rcnt'].array(library='np')[0]==c['scalars']['ca_rcnt']
    before=output.read_bytes()
    with pytest.raises(FileExistsError):
        CONFIG.write_modern_prean_profile(DATA,output,environment_evidence=environment_evidence)
    assert output.read_bytes()==before


@pytest.mark.parametrize('old,new',[
    ('ABGIU = 1.','ABGIU = 2.'),
    ('#if defined(GRAAL_ETA_PI0GG)\n        ABGIU','#if defined(UNKNOWN_BRANCH)\n        ABGIU'),
    ('ABGIU = 1.','ABGIU = 1.\n        ABGIU = 1.'),
])
def test_standard_abgiu_rejects_changed_source(tmp_path,old,new):
    source=ROOT/'docs/reference/fortran/prean/src/constan.F'
    path=tmp_path/'constan.F'
    path.write_text(source.read_text().replace(old,new))
    with pytest.raises(ValueError): CONFIG._standard_abgiu(path)


@pytest.mark.parametrize('replacement',[
    '0.1 0.0 0.0', '0.0 0.0 0.0 0.0', '0.1 1e400 0.0 0.0',
])
def test_selected26_xba1_rejects_invalid_records(tmp_path,replacement):
    (tmp_path/'base').mkdir()
    lines=(DATA/'base/data26.base').read_text().splitlines()
    lines[45]=replacement
    (tmp_path/'base/data26.base').write_text('\n'.join(lines))
    with pytest.raises(ValueError): CONFIG.source_selected26_xba1(tmp_path)


def test_selected26_xba1_lsimul_mean_replacement(tmp_path):
    (tmp_path/'base').mkdir()
    lines=(DATA/'base/data26.base').read_text().splitlines()
    lines[45:77]=['0.25 0.0 0.0 0.0']*31+['2.0 0.0 0.0 0.0']
    path=tmp_path/'base/data26.base'
    path.write_text('\n'.join(lines))
    assert CONFIG.source_selected26_xba1(tmp_path)==[.25]*32
    lines[45:77]=['2.0 0.0 0.0 0.0']*32
    path.write_text('\n'.join(lines))
    with pytest.raises(ValueError,match='average'): CONFIG.source_selected26_xba1(tmp_path)


def test_modern_published_environment_evidence():
    path=ROOT/'docs/reference/fortran/prean-environment-20261110.txt'
    c=CONFIG.read_modern_prean_profile(DATA,environment_evidence=path)
    assert c['modern_initialization']['software_thresholds']['source']['sha256']=='ae7488a1dfcdf2a7721c27236ccaf03e9f21ac4f93101c1abb19248b322da99a'
