"""Resumable angular precomputation and refinement-gated native pilot fit.

prepare records all actual ROOT rows; compute owns one bin and its stages;
fit requires a result for every row, retaining explicit numerical masks.
Separate bin directories allow Slurm tasks without shared-manifest writes.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import fcntl
import json
from pathlib import Path
from time import monotonic

import numpy as np

from graal_theory.angular_basis import AngularBasisIntegrator
from graal_theory.cli import _figure4_model
from graal_theory.figure4_basis import AngularBinCheck, BasisBinCertificate, BasisBinMoment
from graal_theory.figure4_fit import build_exploratory_gls, fit_delta_em
from graal_theory.figure4_fit_output import BasisCheckpoint, fingerprint_inputs, _atomic_bytes
from graal_theory.native_sigma import load_native_sigma_root
from graal_theory.photon_flux import native_flux_spectrum

REFERENCES=Path(__file__).resolve().parents[1]/'references'
POLICY='angular_native_diagnostic_v1'
STAGES=('base','angular','mass','energy','inner')


def write_json(path,value):
    _atomic_bytes(Path(path),(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+ '\n').encode())


def calculate_bin(output,key,fingerprint,stat_error,calculate, *, failure_template, validate_inputs):
    """Save each expensive refinement atomically; interrupted stages alone repeat."""
    output=Path(output)
    def checkpoint(stage):
        path=output/stage
        return BasisCheckpoint.open(path,target='native',keys=(key,),fingerprint=fingerprint,
                                    resume=(path/'manifest.json').exists())
    final=checkpoint('result')
    if not final.pending_keys():
        return final.read(key)
    moments={}
    for name in STAGES:
        saved=checkpoint(name)
        if saved.pending_keys():
            started=monotonic()
            try:
                value=calculate(name)
            except (ValueError,FloatingPointError) as exc:
                value=replace(failure_template,status='masked_nonconverged',
                              reason=f'{name} numerical evaluation: {exc}')
            # A failed provenance check must never be converted into a numerical mask.
            validate_inputs()
            item=BasisBinCertificate(value,'preliminary_uncertified' if value.status=='calculated'
                else value.status,('angular_stage_only',),float('nan'),None,(),0,None)
            saved.write(key,item)
            saved.manifest['elapsed_seconds']=monotonic()-started
            saved.finish()
            print(json.dumps({'key':key,'stage':name,'status':value.status,
                              'seconds':saved.manifest['elapsed_seconds']}),flush=True)
        moments[name]=saved.read(key).moment
        if name=='base' and moments[name].status!='calculated':
            break
    base=moments.pop('base')
    failures=tuple(f'{name}: {value.reason or value.status}' for name,value in moments.items()
                   if value.status!='calculated')
    item=AngularBinCheck(base,'diagnostic_converged',(),moments,min(.01,.2*stat_error))
    if base.status!='calculated':
        item=replace(item,status=base.status,reason=(base.reason or base.status,))
    elif failures:
        item=replace(item,status='masked_nonconverged',reason=failures)
    else:
        failures=[]
        for coefficients in ([1.,0.,0.],[1.,.08,-.04],[1.,-.06,.05]):
            try:
                item.predict(coefficients)
            except (ValueError,FloatingPointError) as exc:
                failures.append(str(exc))
        if failures:
            item=replace(item,status='masked_nonconverged',reason=tuple(dict.fromkeys(failures)))
    validate_inputs()
    final.write(key,item); final.finish()
    return item


def input_paths(args):
    import graal_theory
    package=REFERENCES.parent/'src'/'graal_theory'
    if Path(graal_theory.__file__).resolve().parent != package.resolve():
        raise ValueError('executing source imports differ from workflow snapshot')
    paths={f'code/{p.relative_to(package)}':p for p in package.rglob('*.py')}
    paths.update({f'references/{p.name}':p for p in REFERENCES.glob('*.json')})
    paths['workflow']=Path(__file__).resolve()
    paths.update({name:Path(getattr(args,name)).resolve() for name in
                  ('data_root','reco_root','flux_root','run_manifest')})
    paths["extraction_index"]=paths["data_root"].parent/"periods"/"index.json"
    return paths


def prepare(args):
    import uproot
    output=args.campaign
    if (output/'campaign.json').exists():
        raise FileExistsError('campaign already prepared; use compute to resume')
    if any(type(n) is not int or n<2 for n in (args.energy_order,args.mass_order,args.angular_order)):
        raise ValueError('quadrature orders must be integers >= 2')
    paths=input_paths(args)
    extraction=json.loads(paths['extraction_index'].read_text())
    if (extraction.get('universe_source')!='reconstruction_cutflow'
            or extraction.get('profile')!='uv'
            or extraction.get('command_options',{}).get('nominal_sample')!='raw_bdt'
            or (extraction.get('run_quality') or {}).get('excluded_runs')):
        raise ValueError('unsupported native extraction run-universe policy')
    data=load_native_sigma_root(paths['data_root'])
    if data.status!='pilot':
        raise ValueError('angular workflow requires explicitly pilot data')
    settings=dict(policy=POLICY,energy_order=args.energy_order,mass_order=args.mass_order,
                  angular_order=args.angular_order,q_order=64,angle_order=48,
                  inner_q_order=96,inner_angle_order=72,mode='direct',
                  keys=[list(k) for k in data.keys])
    before=fingerprint_inputs('native',paths,settings)
    # Match actual ROOT exposure normalization, not just nominal energy edges.
    fields=('flux_vertical','flux_horizontal','polarization_vertical','polarization_horizontal')
    with uproot.open(paths['data_root']) as source:
        columns=source['sigma_points'].arrays(fields,library='np')
    exposure_audit={}
    for energy in sorted({key[1] for key in data.keys}):
        interval=tuple(map(float,data.energy_edges_gev[energy:energy+2]))
        spectrum=native_flux_spectrum(paths['flux_root'],paths['run_manifest'],paths['reco_root'],interval,use_inclusive_cutflow=True)
        fv=sum(n.flux_vertical for n in spectrum.exposures)
        fh=sum(n.flux_horizontal for n in spectrum.exposures)
        pv=sum(n.flux_vertical*n.polarization_vertical for n in spectrum.exposures)/fv
        ph=sum(n.flux_horizontal*n.polarization_horizontal for n in spectrum.exposures)/fh
        indices=[int(data.tree_indices[i]) for i,key in enumerate(data.keys) if key[1]==energy]
        for field,expected in zip(fields,(fv,fh,pv,ph)):
            if not np.allclose(columns[field][indices],expected,rtol=1e-9,atol=1e-12):
                raise ValueError(f'native exposure mismatch at energy bin {energy}: {field}; '
                                 f'theory={expected}, ROOT={columns[field][indices].tolist()}')
        exposure_audit[str(energy)]=dict(zip(fields,(fv,fh,pv,ph)),
            source_fingerprint=spectrum.source_fingerprint,selected_runs=spectrum.selected_runs,
            complete_runs=spectrum.complete_runs)
    if fingerprint_inputs('native',paths,settings)!=before:
        raise ValueError('inputs changed during preparation')
    manifest=dict(policy=POLICY,fingerprint=before,settings=settings,
                  inputs={name:str(path.resolve()) for name,path in paths.items()},
                  data_sha256=data.source_sha256,provenance=data.provenance,
                  exposure_audit=exposure_audit,
                  phi_bins=data.phi_bins.tolist(),phi_bin_divisor=data.phi_bin_divisor.tolist(),
                  ratio_used_fallback=data.ratio_used_fallback.tolist())
    output.mkdir(parents=True,exist_ok=True)
    write_json(output/'campaign.json',manifest)
    _atomic_bytes(output/'keys.txt',(''.join(f'{pair}:{energy}:{mass}\n' for pair,energy,mass in data.keys)).encode())
    print(json.dumps({'prepared':str(output),'bins':len(data.keys),'fingerprint':before}),flush=True)
    return 0


def load_campaign(path):
    manifest=json.loads((Path(path)/'campaign.json').read_text())
    if manifest.get('policy')!=POLICY:
        raise ValueError('incompatible angular campaign policy')
    paths={name:Path(p) for name,p in manifest['inputs'].items()}
    executing=input_paths(argparse.Namespace(**paths))
    if {name:p.resolve() for name,p in paths.items()} != {name:p.resolve() for name,p in executing.items()}:
        raise ValueError('executing source/reference tree differs from campaign snapshot')
    if fingerprint_inputs('native',paths,manifest['settings'])!=manifest['fingerprint']:
        raise ValueError('campaign source/data/settings fingerprint changed')
    data=load_native_sigma_root(paths['data_root'])
    if (data.source_sha256!=manifest['data_sha256'] or data.status!='pilot'
            or [list(k) for k in data.keys]!=manifest['settings']['keys']):
        raise ValueError('campaign data identity changed')
    return manifest,paths,data


def compute(args):
    manifest,paths,data=load_campaign(args.campaign)
    pair,energy,mass=args.key.split(':'); key=(pair,int(energy),int(mass))
    if key not in data.keys:
        raise ValueError('key not in actual native points')
    index=data.keys.index(key); energy,mass=key[1:]
    storage_key=(energy,pair,mass)
    out=args.campaign/'precompute'/f'{energy}_{pair}_{mass}'
    out.mkdir(parents=True,exist_ok=True)
    with (out/'compute.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        interval=tuple(map(float,data.energy_edges_gev[energy:energy+2]))
        target=tuple(map(float,data.mass_edges_gev[pair][mass:mass+2]))
        spectrum=native_flux_spectrum(paths['flux_root'],paths['run_manifest'],paths['reco_root'],interval,use_inclusive_cutflow=True)
        settings=manifest['settings']; integrators={}
        def calculate(stage):
            inner=stage=='inner'
            if inner not in integrators:
                integrators[inner]=AngularBasisIntegrator(_figure4_model(REFERENCES,'direct',
                    settings['inner_q_order' if inner else 'q_order'],
                    settings['inner_angle_order' if inner else 'angle_order']))
            return integrators[inner].integrate_bin(pair,interval,target,energy_rule='native_flux',
                energy_order=settings['energy_order']*(2 if stage=='energy' else 1),
                mass_order=settings['mass_order']*(2 if stage=='mass' else 1),
                angular_order=settings['angular_order']*(2 if stage=='angular' else 1),
                flux_spectrum=spectrum,phi_bins=int(data.phi_bins[index]),
                phi_bin_divisor=float(data.phi_bin_divisor[index]),
                ratio_used_fallback=bool(data.ratio_used_fallback[index]))
        zero=np.zeros((3,3),complex)
        failure_template=BasisBinMoment(pair,interval,target,'native_flux',zero,zero.copy(),
            None,None,None,None,None,zero.copy(),np.empty(0),'masked_nonconverged',
            phi_bin_divisor=float(data.phi_bin_divisor[index]),
            ratio_used_fallback=bool(data.ratio_used_fallback[index]))
        item=calculate_bin(out,storage_key,manifest['fingerprint'],float(data.stat_error[index]),calculate,
                           failure_template=failure_template,
                           validate_inputs=lambda:load_campaign(args.campaign))
        load_campaign(args.campaign)  # Refuse changed source or inputs, even during long jobs.
        print(json.dumps({'key':key,'status':item.status,'reason':item.reason}),flush=True)
    return 0


def load_results(path,manifest,data):
    results={}
    for pair,energy,mass in data.keys:
        folder=Path(path)/'precompute'/f'{energy}_{pair}_{mass}'/'result'
        if not (folder/'manifest.json').is_file():
            raise ValueError(f'incomplete campaign: missing {pair}:{energy}:{mass}')
        saved=json.loads((folder/'manifest.json').read_text())
        if saved.get('fingerprint')!=manifest['fingerprint'] or not saved.get('complete'):
            raise ValueError('incomplete or incompatible bin checkpoint')
        item=BasisCheckpoint(folder,saved).read((energy,pair,mass))
        if not isinstance(item,AngularBinCheck):
            raise ValueError('expected angular diagnostic checkpoint')
        moment=item.moment
        if (moment.pair!=pair or moment.energy_rule!='native_flux'
                or moment.energy_range_gev!=tuple(data.energy_edges_gev[energy:energy+2])
                or moment.mass_range_gev!=tuple(data.mass_edges_gev[pair][mass:mass+2])):
            raise ValueError('checkpoint native bin identity mismatch')
        results[(pair,energy,mass)]=item
    return results


def fit(args):
    manifest,paths,data=load_campaign(args.campaign)
    results=load_results(args.campaign,manifest,data)
    moments={key:item.moment if item.status=='diagnostic_converged' else
             replace(item.moment,status=item.status,reason='; '.join(item.reason))
             for key,item in results.items()}
    objective=build_exploratory_gls(data,moments,checks=results)
    result=fit_delta_em(objective,np.array([objective.anchor_g1,objective.anchor_g2]))
    report={name:value.tolist() if isinstance(value,np.ndarray) else value
            for name,value in asdict(result).items()}
    report.update(policy=POLICY,purpose='refinement_gated_pilot_only',
        data_provenance=data.provenance,campaign_fingerprint=manifest['fingerprint'],
        included_bins=len(objective.data.keys),total_bins=len(data.keys),
        excluded=[{'key':key,'reason':reason} for key,reason in objective.excluded],
        limitations=['deterministic refinement evidence, not production certification',
                     'background uncorrected; run bootstrap absent; final inference suspended'])
    output=args.campaign/'fit.json'
    if output.exists():
        raise FileExistsError('fit report already exists')
    write_json(output,report)
    print(json.dumps({'status':result.status,'included':len(objective.data.keys),
                      'chi_square':result.chi_square,'report':str(output)}),flush=True)
    return 0 if result.status=='exploratory_pilot' else 2


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    prep=commands.add_parser('prepare')
    for name in ('data-root','reco-root','flux-root','run-manifest'):
        prep.add_argument('--'+name,type=Path,required=True)
    prep.add_argument('--energy-order',type=int,default=4)
    prep.add_argument('--mass-order',type=int,default=16)
    prep.add_argument('--angular-order',type=int,default=8)
    calc=commands.add_parser('compute'); calc.add_argument('--key',required=True)
    commands.add_parser('fit')
    for command in commands.choices.values():
        command.add_argument('--campaign',type=Path,required=True)
    args=parser.parse_args(argv)
    return {'prepare':prepare,'compute':compute,'fit':fit}[args.command](args)


if __name__=='__main__':
    raise SystemExit(main())
