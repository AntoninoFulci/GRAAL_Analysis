"""Explicit initialized LSIMUL BGO/barrel reconstruction configuration.

Runtime STHRES/CTHRES/ABGIU and CA RCNT/TDE are never guessed. Measured ADC
scales belong to legacy09 response, independently of selected26 geometry.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile

from mc_simulation.geant4.legacy_response import _f15_3 as _response_f15_3

_ROOT=Path(__file__).resolve().parents[2]
_FORTRAN=_ROOT/'docs/reference/fortran/prog'
_PREAN_SOURCE=_ROOT/'docs/reference/fortran/prean/src'
_REAL=re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?')
SCALE_RECORDS={
    'bgo_adc_channels':(2,'SCBGO'), 'bgo_adc_fullscale_gev':(3,'VSCBGO'),
    'barrel_adc_channels':(40,'SCDEB'), 'barrel_adc_fullscale_gev':(41,'VSCDEB'),
    'barrel_tdc_channels':(152,'SDETOF'), 'barrel_tdc_fullscale_seconds':(153,'VDETOF')}


def _real(value):
    if isinstance(value,bool): raise ValueError('Boolean is not a REAL parameter')
    if isinstance(value,str): value=value.replace('D','E').replace('d','e')
    try: value=struct.unpack('f',struct.pack('f',float(value)))[0]
    except (OverflowError,ValueError,TypeError,struct.error) as error:
        raise ValueError('Parameter outside binary32 domain') from error
    if not math.isfinite(value): raise ValueError('Nonfinite binary32 parameter')
    return value


def _source(path):
    path=Path(path).resolve()
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def _f15_3(line,label):
    if len(line)<15 or '!' not in line or not re.match(r'\s*'+re.escape(label)+r'(?:\s|=|$)',line.split('!',1)[1]):
        raise ValueError(f'Missing source field {label}')
    return _real(_response_f15_3(line))


def source_selected26_xba1(data_directory):
    """CONSTAN LSIMUL attenuation initialization; independent explicit choice."""
    lines=(Path(data_directory)/'base/data26.base').read_text().splitlines()
    if len(lines)<77 or 'Calibration of attenuation in DE/DX' not in lines[43]:
        raise ValueError('Missing selected26 barrel attenuation records')
    values=[]
    for line in lines[45:77]:
        tokens=line.split()
        if len(tokens)!=4 or any(not _REAL.fullmatch(v) for v in tokens):
            raise ValueError('Malformed selected26 barrel attenuation record')
        row=[_real(token) for token in tokens]
        if row[0]<=0: raise ValueError('Nonpositive selected26 XBA1 coefficient')
        values.append(row[0])
    total=_real(0); count=0
    for value in values:
        if value<=1: total=_real(total+value); count+=1
    if not count: raise ValueError('Undefined CONSTAN XBA1 average')
    mean=_real(total/count)
    return [mean if value>1 else value for value in values]


def _fortran_code(path):
    """Drop fixed-form comments and inline comments; retain CPP directives."""
    return '\n'.join(line.split('!',1)[0].rstrip() for line in Path(path).read_text().splitlines()
                     if line and line[0] not in 'Cc*!')


def _read_ca_tables(path):
    """Read the sole active INIT_CA tables, excluding commented alternatives."""
    text=_fortran_code(path)
    tables={}
    for symbol,key in (('SOG','sog_gev'),('RCNT1','rcnt'),('TDE1','tde')):
        matches=list(re.finditer(r'^\s*DATA\s+'+symbol+r'\s*/([^/\n]*)/\s*$',text,re.M))
        declarations=re.findall(r'^\s*DATA\s+'+symbol+r'\b',text,re.M)
        if len(matches)!=1 or len(declarations)!=1:
            raise ValueError(f'Expected one active INIT_CA {symbol} table')
        # Source tables precede all conditional code; never infer a CPP branch.
        if re.search(r'^\s*#\s*(?:if|elif|else)',text[:matches[0].start()],re.M):
            raise ValueError('Conditional INIT_CA tables are unsupported')
        tokens=matches[0].group(1).split(',')
        if len(tokens)!=6 or any(not _REAL.fullmatch(v.strip()) for v in tokens):
            raise ValueError(f'Malformed INIT_CA {symbol} table')
        tables[key]=[_real(v.strip()) for v in tokens]
    if any(a>=b for a,b in zip(tables['sog_gev'],tables['sog_gev'][1:])):
        raise ValueError('INIT_CA SOG must be strictly increasing')
    if any(v<=0 for values in tables.values() for v in values):
        raise ValueError('INIT_CA table values must be positive')
    for target,table in (('RCNT','RCNT1'),('TDE','TDE1')):
        calls=re.findall(r'^\s*'+target+r'\s*=\s*(.*?)\s*$',text,re.M)
        if calls!=[f'DIVDIF({table},SOG,6,THRES,1)']:
            raise ValueError(f'Unsupported INIT_CA {target} interpolation source')
    return tables


def _linear_binary32(threshold,knots,values):
    """Modern linear interpolation with explicit binary32 operation rounding."""
    x=_real(threshold)
    if len(knots)!=len(values) or len(knots)<2 or any(a>=b for a,b in zip(knots,knots[1:])):
        raise ValueError('Invalid interpolation table')
    if not knots[0]<=x<=knots[-1]: raise ValueError('THRES outside INIT_CA SOG range')
    for i,knot in enumerate(knots):
        if x==knot: return values[i]
        if x<knot:
            fraction=_real(_real(x-knots[i-1])/_real(knot-knots[i-1]))
            return _real(values[i-1]+_real(fraction*_real(values[i]-values[i-1])))
    raise ValueError('Invalid interpolation domain')


def _modern_environment(path):
    """Validate supplied shell evidence without executing any of its contents."""
    text=Path(path).read_text()
    result={}
    for variable,expected in (('BGO_SOFT_THRES',.002),('CLUS_SOFT_THRES',.015)):
        exports=re.findall(r'^\s*export\s+'+variable+r'=([^\s#]+)\s*(?:#.*)?$',text,re.M)
        echoes=re.findall(r'\becho\s+\$'+variable+r'\s*\n([^\n]*)',text)
        tokens=exports+echoes
        if not exports or any(not _REAL.fullmatch(v.strip()) for v in tokens):
            raise ValueError(f'Missing or malformed environment evidence: {variable}')
        values=[_real(v.strip()) for v in tokens]
        if any(v!=_real(expected) for v in values):
            raise ValueError(f'Conflicting or unsupported environment evidence: {variable}')
        result[variable]=values[0]
    return result


def _standard_abgiu(path):
    text=_fortran_code(path)
    pattern=(r'^\s*ABGIU\s*=\s*('+_REAL.pattern+r')\s*\n'
             r'#if defined\(GRAAL_ETA_PI0GG\)\s*\n'
             r'\s*ABGIU\s*=\s*('+_REAL.pattern+r')\s*\n#endif')
    matches=re.findall(pattern,text,re.M)
    assignments=re.findall(r'^\s*ABGIU\s*=.*$',text,re.M)
    if len(matches)!=1 or len(assignments)!=2:
        raise ValueError('Unsupported CONSTAN ABGIU branch structure')
    standard,eta=map(_real,matches[0])
    if standard!=1 or eta!=2.5: raise ValueError('Unexpected CONSTAN ABGIU branch values')
    return standard


def read_modern_prean_profile(data_directory, *, environment_evidence, enable_sp=True):
    """Named deterministic initialization; not a reconstruction of old runtime state.

    Read database THRES before interpolating INIT_CA, explicitly assign the
    standard ABGIU branch also for LSIMUL, and retain independent legacy09 digit
    scales. No CERNLIB DIVDIF bit-for-bit equivalence is claimed.
    """
    environment=_modern_environment(environment_evidence)
    database=Path(data_directory)/'base/data26.base'
    lines=database.read_text().splitlines()
    if len(lines)<4: raise ValueError('Missing selected26 THRES record')
    threshold=_f15_3(lines[3],'THRES')
    init_ca=_PREAN_SOURCE/'init_ca.F'; constan=_PREAN_SOURCE/'constan.F'
    tables=_read_ca_tables(init_ca)
    rcnt=_linear_binary32(threshold,tables['sog_gev'],tables['rcnt'])
    tde=_linear_binary32(threshold,tables['sog_gev'],tables['tde'])
    abgiu=_standard_abgiu(constan)
    config=read_bgo_config(data_directory,crystal_threshold=environment['BGO_SOFT_THRES'],
        cluster_threshold=environment['CLUS_SOFT_THRES'],barrel_energy_threshold_mev=abgiu,
        ca_rcnt=rcnt,ca_tde=tde,xba1=source_selected26_xba1(data_directory),
        initialization_claim='Modern explicit PREAN initialization from declared source tables and supplied environment evidence; not historical runtime reproduction',
        enable_sp=enable_sp)
    config['initialization_policy']='Read selected26 THRES before INIT_CA; explicitly initialize standard ABGIU also for LSIMUL; use supplied software thresholds and selected26 XBA1; legacy09 digit scales remain independent'
    config['modern_initialization']=dict(
        profile='modern_prean_selected26_pi0_v1',historical_runtime_reproduction=False,
        initialization_order=['read selected26 THRES','interpolate INIT_CA RCNT/TDE',
                              'assign standard ABGIU for LSIMUL','assign software thresholds and selected26 XBA1'],
        assumptions=['GRAAL_ETA_PI0GG undefined; standard ABGIU explicitly assigned for simulation',
                     'GRAAL_RUN_SLAVA undefined; software thresholds from supplied environment evidence',
                     'Active pi0 RCNT1 table selected, including for this diagnostic reaction',
                     'Modern deterministic initialization replaces unavailable pre-CONSTAN runtime state'],
        software_thresholds=dict(values=environment,units='GeV',source=_source(environment_evidence)),
        abgiu=dict(value=abgiu,units='MeV',GRAAL_ETA_PI0GG=False,assigned_for_lsimul=True,
                   source=_source(constan)),
        ca=dict(threshold_symbol='THRES',threshold_gev=threshold,threshold_record=4,
                threshold_format='F15.3',threshold_source=_source(database),tables=tables,
                source=_source(init_ca),rcnt=rcnt,tde=tde,
                units=dict(sog_gev='GeV',rcnt='dimensionless',tde='dimensionless'),
                interpolation='Piecewise linear, exact knots returned; reject extrapolation',
                formula='y0 + ((THRES - x0) / (x1 - x0)) * (y1 - y0)',
                rounding='IEEE-754 binary32 inputs and each subtraction, division, multiplication and addition; modern rounding policy, not verified against CERNLIB DIVDIF'),
        xba1=dict(source=_source(database),records=[46,77],units='source attenuation coefficient',
                  policy='CONSTAN LSIMUL: replace values >1 with binary32 mean of values <=1'))
    known={item['path'] for item in config['sources']}
    for path in (database,init_ca,constan,environment_evidence):
        source=_source(path)
        if source['path'] not in known:
            config['sources'].append(source); known.add(source['path'])
    return config


def read_bgo_config(data_directory, *, crystal_threshold, cluster_threshold,
                    barrel_energy_threshold_mev, ca_rcnt, ca_tde, xba1,
                    initialization_claim, enable_sp=True):
    """Require declared initialized state; this is not an historical run profile."""
    if not isinstance(initialization_claim,str) or not initialization_claim.strip():
        raise ValueError('Explicit initialization_claim is required')
    if type(enable_sp) is not bool: raise ValueError('enable_sp must be boolean')
    scalars={key:_real(value) for key,value in dict(crystal_threshold=crystal_threshold,
        cluster_threshold=cluster_threshold,barrel_energy_threshold_mev=barrel_energy_threshold_mev,
        ca_rcnt=ca_rcnt,ca_tde=ca_tde).items()}
    if any(scalars[k]<0 for k in ('crystal_threshold','cluster_threshold','barrel_energy_threshold_mev')):
        raise ValueError('Thresholds must be nonnegative')
    attenuation=[_real(v) for v in xba1]
    if len(attenuation)!=32: raise ValueError('Exactly 32 explicit XBA1 values required')
    database=Path(data_directory)/'base/data09.base'
    lines=database.read_text().splitlines()
    for key,(record,label) in SCALE_RECORDS.items():
        if len(lines)<record: raise ValueError(f'Truncated legacy09 database at {label}')
        scalars[key]=_f15_3(lines[record-1],label)
        if scalars[key]<=0: raise ValueError(f'Nonpositive ADC/TDC scale {label}')
    scalars['enable_sp']=enable_sp
    block=_FORTRAN/'prean/src/blockdata.F'
    text=block.read_text()
    def values(pattern,count):
        match=re.search(pattern,text,re.S)
        if not match: raise ValueError('Missing source BLOCKDATA table')
        tokens=match.group(1).replace('&','').split(',')
        if len(tokens)!=count or any(not _REAL.fullmatch(v.strip()) for v in tokens):
            raise ValueError('Malformed source BLOCKDATA table')
        return [_real(v.strip()) for v in tokens]
    theta=values(r'DATA TET/(.*?)/',15); volume=values(r'DATA VOL/(.*?)/',15)
    phi=values(r'DATA PHI/(.*?)/',32)
    correction={}
    for key in ('A','B'):
        correction[key.lower()]=sum((values(r'DATA \(PARAM_CORR_'+key+r'\(J,'+str(i)+r'\),J=1,12\) /(.*?)/',12) for i in range(1,9)),[])
    paths=[database,block]
    paths.extend(_FORTRAN/'prean/src'/f'{name}.F' for name in (
        'anabgo','anabar','calc_clust','bgo_energy','bgo_energy_correction','sigma_xy_old',
        'sigma_xy_new','clus_flag','init_ca','constan','read_option','find_track_cbb',
        'associa_2_new','associa_3_new','delta_phi'))
    paths.extend(_FORTRAN/'prean/include'/f'{name}.inc' for name in (
        'angle','coeff','corr_eg_bgo','clus','bgo','barrel','barrel_calibr','pm_b_b','prean_const',
        'event','lflag','kpbgo','pcn','att_wall','ass_cbb','parametres_cylindres','traces_cylindres'))
    paths.append(_FORTRAN/'prean/pilot.h')
    ca=_ROOT/'docs/reference/fortran/lib_cluster_c'
    paths.extend(sorted((ca/'src').glob('*.c')))
    paths.extend(sorted((ca/'include').glob('*.h')))
    paths.append(ca/'pilot.h')
    return dict(schema=1,mode='selected26_central_reconstruction_diagnostic',
        physical_validation=False,physics_validation=False,simulation=True,
        digit_decode_profile='legacy09',geometry_profile='selected26',
        initialization_claim=initialization_claim,
        initialization_policy='Explicit initialized thresholds, CA parameters and XBA1; unavailable historical environment and pre-CONSTAN INIT_CA state are not inferred',
        units=dict(bgo_energy='GeV',barrel_energy='MeV',barrel_time='ns',angles='degree'),
        baseline=['LSIMUL','GRAAL_BGO_SP' if enable_sp else 'NO_GRAAL_BGO_SP','April1998_energy_correction'],
        scalars=scalars,theta=dict(index=list(range(1,16)),theta=theta,volume=volume),
        phi=dict(index=list(range(1,33)),phi=phi,xba1=attenuation),
        corrections=dict(index=list(range(96)),**correction),sources=[_source(p) for p in paths],
        undefined_domains=['SIGMA_XY_OLD abs(DD)<1e-10 and XNN=0: old shapes unavailable; other observables retained',
                           'BGO energy correction theta outside source table: rejected',
                           'CA source undefined membership paths: see CA status'])


def write_bgo_config(data_directory,output_root,**settings):
    """Write fresh typed config, atomically; never replace an existing file."""
    output=Path(output_root)
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    return _write_config(output,read_bgo_config(data_directory,**settings))


def write_modern_prean_profile(data_directory,output_root,*,environment_evidence,enable_sp=True):
    """Publish the named modern initialization and full provenance as ROOT."""
    output=Path(output_root)
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    return _write_config(output,read_modern_prean_profile(data_directory,
                         environment_evidence=environment_evidence,enable_sp=enable_sp))


def _write_config(output,config):
    import numpy as np
    import uproot
    if output.exists() or output.is_symlink(): raise FileExistsError(output)
    fd,name=tempfile.mkstemp(prefix=f'.{output.name}.',suffix='.partial',dir=output.parent)
    os.close(fd); partial=Path(name)
    try:
        with uproot.recreate(partial,compression=uproot.ZSTD(5)) as root:
            types={key:('bool' if key=='enable_sp' else 'float32') for key in config['scalars']}
            root.mktree('scalars',types).extend({key:np.asarray([value],dtype=types[key]) for key,value in config['scalars'].items()})
            for name in ('theta','phi','corrections'):
                types={key:('int32' if key=='index' else 'float32') for key in config[name]}
                root.mktree(name,types).extend({key:np.asarray(value,dtype=types[key]) for key,value in config[name].items()})
            root['metadata']=json.dumps(config,sort_keys=True,allow_nan=False)
        with partial.open('rb') as stream: os.fsync(stream.fileno())
        os.link(partial,output)
    finally: partial.unlink(missing_ok=True)
    return config
