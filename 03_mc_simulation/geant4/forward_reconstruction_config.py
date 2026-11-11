"""Explicit selected26 measured-forward reconstruction profile.

IDRUN is a caller-supplied source condition, independent of both calibration
run selectors and the G4 event key. No default simulation IDRUN is inferred.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile

_HERE=Path(__file__).resolve().parent
_ROOT=_HERE.parents[1]
_FORTRAN=_ROOT/'docs/reference/fortran/prog'
_spec=importlib.util.spec_from_file_location('_forward_response_config',_HERE/'forward_config.py')
_response=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_response)
GEOMETRY_RECORDS={'zp1_cm':(86,'ZP1'),'zp2_cm':(87,'ZP2'),'zp3_cm':(165,'ZP3')}


def read_selected26_forward_reconstruction(data_directory, *, source_run, source_directory=None):
    if type(source_run) is not int or not 0 <= source_run <= 65535:
        raise ValueError('source_run must be an explicitly supplied unsigned16 source IDRUN')
    data=Path(data_directory);source=Path(source_directory) if source_directory else _FORTRAN
    out=_response.read_selected26_forward(data,source_directory=source)
    raw=(data/'base/data26.base').read_bytes();lines=raw.decode('ascii').splitlines();scalars={}
    for key,(record,label) in GEOMETRY_RECORDS.items():
        if len(lines)<record or not re.match(r'\s*'+label+r'(?:\s|$)',lines[record-1].split('!',1)[-1]):
            raise ValueError(f'Missing selected26 geometry label {label} at record{record}')
        field=lines[record-1][:15].strip()
        if len(lines[record-1])<15 or not _response._REAL.fullmatch(field):
            raise ValueError(f'Malformed CONSTAN F15.3 geometry {label}')
        # Fortran F15.3 supplies the implied decimal only when absent, including
        # exponent notation. Parse exponent separately to match formatted READ.
        value=float(field.replace('D','E').replace('d','e'))
        if '.' not in field:value/=1000
        scalars[key]=_response._real(format(value,'.17g'))
    if not 0<scalars['zp1_cm']<scalars['zp2_cm']<scalars['zp3_cm']:
        raise ValueError('Nonpositive/unordered selected26 forward geometry')
    scalars.update(source_run=source_run,rf_bunch=0,simulation=True)
    out['mode']='selected26_forward_reconstruction_diagnostic'
    out['reconstruction']=scalars
    out['geometry_records']={k:v[0] for k,v in GEOMETRY_RECORDS.items()}
    out['sources'].append(dict(path='data/base/data26.base',sha256=hashlib.sha256(raw).hexdigest()))
    for name in ('wall_clus','wall_var','wall_ass_w1_w2','double_bar','russwall','ana_wal','wall_att','analysis','find_track','constan','readevents'):
        path=f'prean/src/{name}.F'
        out['sources'].append(dict(path=path,sha256=hashlib.sha256((source/path).read_bytes()).hexdigest()))
    out['source_run_policy']='explicit caller IDRUN profile; original LAGWREV uses GEANT3 gcflag IDRUN, PREAN reads ntuple; never inferred from WALL4300 or RW340 calibration'
    out['rf_policy']='simulation IND_BUNCH_RF=0, prean/src/analysis.F'
    out['source_undefined_domains']=['WALL_CLUS >=2 accepted H and zero accepted V: TH_DIF','RUSSWALL recognized hit with planar+V but zero raw H: EOWLIM','RUSSWALL planar alignment for IDRUN833 or simulation834..2241','active source array bounds and nonfinite output']
    out['baseline']+=['GRAAL_WALL_ALESSIA','GRAAL_RUSSWALL2','GRAAL_TRACK_ALESSIA','GRAAL_NEW_PLAN']
    out['units'].update(wall_tof='ns',wall_de='MeV',shower_tof='s',shower_energy='GeV',final_tof='ns',final_de='MeV')
    return out


def write_forward_reconstruction_config(data_directory, output_root, *, source_run):
    """Publish fresh response+reconstruction tables with reviewable metadata."""
    import numpy as np
    import uproot
    output=Path(output_root)
    if output.exists() or output.is_symlink():raise FileExistsError(output)
    config=read_selected26_forward_reconstruction(data_directory,source_run=source_run)
    fd,name=tempfile.mkstemp(prefix=f'.{output.name}.',suffix='.partial',dir=output.parent);os.close(fd);partial=Path(name)
    try:
        with uproot.recreate(partial,compression=uproot.ZSTD(5)) as root:
            def table(name,values):
                tree=root.mktree(name,{k:'float32' for k in values});tree.extend({k:np.asarray(v,dtype='float32') for k,v in values.items()})
            table('wall',config['wall'])
            table('shower',{k:v for k,v in config['shower'].items() if k!='ay'})
            table('simulation_rw',{k:v for k,v in config['simulation_rw'].items() if k!='ay'})
            table('scalars',{'shower_ay':[config['shower']['ay']],'simulation_rw_ay':[config['simulation_rw']['ay']]})
            for key,values in config['attenuation'].items():table(key,{'coefficient':values})
            types={k:'float32' for k in GEOMETRY_RECORDS};types.update(source_run='int32',rf_bunch='int32',simulation='bool')
            root.mktree('reconstruction',types).extend({k:np.asarray([v],dtype=types[k]) for k,v in config['reconstruction'].items()})
            root['metadata']=json.dumps(config,sort_keys=True,allow_nan=False)
        with partial.open('rb') as stream:os.fsync(stream.fileno())
        os.link(partial,output)
    finally:partial.unlink(missing_ok=True)
    return config
