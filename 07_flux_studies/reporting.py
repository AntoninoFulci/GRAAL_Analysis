"""Exclusive publication and portable diagnostic serialization."""
from __future__ import annotations

from contextlib import contextmanager
import csv
import json
import math
from pathlib import Path

import numpy as np
from calibration.calibration_qa import sha256_file
from graal_common.io.filesystem import atomic_output_directory


def json_value(value):
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, np.ndarray)):
        return [json_value(v) for v in value]
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(json_value(value), indent=2, sort_keys=True, allow_nan=False) + '\n')


def write_csv(path, rows):
    rows = list(rows)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(json_value(v), allow_nan=False) if isinstance(v, (list, tuple, dict, np.ndarray)) else json_value(v)
                             for k, v in row.items()})


@contextmanager
def publish_output(destination: Path, inputs):
    destination = Path(destination)
    resolved = destination.resolve()
    sources = [Path(p) for p in inputs if p is not None]
    for source in sources:
        real = source.resolve(strict=True)
        if real == resolved or resolved in real.parents:
            raise ValueError(f'output overlaps input: {source}')
        if destination.exists() and destination.samefile(source):
            raise ValueError(f'output aliases input: {source}')
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f'output already exists: {destination}')
    before = {str(p): sha256_file(p) for p in sources}
    with atomic_output_directory(destination, overwrite=False) as staged:
        yield staged
        after = {str(p): sha256_file(p) for p in sources}
        if before != after:
            raise ValueError('input changed during study; publication cancelled')
        write_json(staged / 'input_integrity.json', dict(before=before, after=after, unchanged=True))


def write_audit(directory: Path, result: dict):
    write_json(directory / 'audit.json', {key: value for key, value in result.items()
                                        if key not in ('histograms', 'metadata', 'strips', 'rows')})
    write_csv(directory / 'inventory.csv', result['rows'])
    write_csv(directory / 'strip_inventory.csv', result['strips'])


def _public_prediction(row):
    return {k: v for k, v in row.items() if k not in ('context_id',)}


def _root_histogram(root, directory, name, values):
    directory.cd()
    hist = root.TH1D(name, name, len(values), 0., float(len(values)))
    for i, value in enumerate(values, start=1):
        hist.SetBinContent(i, float(value))
    hist.Write()


def _root_records(path, predictions, uncertainty, provenance, namespace):
    import ROOT
    from array import array
    output = ROOT.TFile(str(path), 'RECREATE')
    if not output or output.IsZombie():
        raise OSError(f'cannot write ROOT: {path}')
    try:
        meta = output.mkdir('metadata'); meta.cd()
        ROOT.TObjString(json.dumps(json_value(provenance), allow_nan=False)).Write('provenance')
        records = output.mkdir(namespace)
        measured = output.mkdir('measured') if namespace == 'holdout' else None
        for index, row in enumerate(predictions):
            directory = records.mkdir(f'p{index:06d}'); directory.cd()
            ROOT.TObjString(json.dumps(json_value(_public_prediction(row)), allow_nan=False)).Write('metadata')
            if row['estimate'] is not None:
                _root_histogram(ROOT, directory, 'estimate', row['estimate'])
            if row.get('truth') is not None:
                _root_histogram(ROOT, directory, 'truth', row['truth'])
                _root_histogram(ROOT, measured, f'p{index:06d}', row['truth'])
            covariance = uncertainty['covariance'].get(index)
            if covariance is not None:
                directory.cd()
                hist = ROOT.TH2D('covariance', 'predictive covariance', 128, 0, 128, 128, 0, 128)
                for x, y in np.ndindex(covariance.shape):
                    hist.SetBinContent(x+1, y+1, float(covariance[x,y]))
                hist.Write()
        directory = output.mkdir('uncertainty'); directory.cd()
        tree = ROOT.TTree('replicas', 'Aligned draws; invalid predictions have valid=0')
        replica, target, valid, mean_valid = (array('i',[0]) for _ in range(4))
        values, mean = array('d',[0.]*128), array('d',[0.]*128)
        for name, buffer in [('replica',replica),('target',target),('valid',valid),('mean_valid',mean_valid)]:
            tree.Branch(name,buffer,f'{name}/I')
        tree.Branch('values',values,'values[128]/D');tree.Branch('mean',mean,'mean[128]/D')
        for ri in range(len(uncertainty['replica_ids'])):
            for pi in range(len(predictions)):
                replica[0],target[0]=ri,pi
                valid[0]=int(uncertainty['valid'][ri,pi])
                draws=uncertainty['replicas'][ri,pi]
                means=uncertainty['mean_replicas'][ri,pi]
                mean_valid[0]=int(np.all(np.isfinite(means)))
                for strip in range(128):values[strip]=float(draws[strip]);mean[strip]=float(means[strip])
                tree.Fill()
        tree.Write()
    finally:
        output.Close()


def _study_plots(directory, audit, study):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from flux_studies.metadata import compatible
    plots = directory/'plots';plots.mkdir(exist_ok=True)
    predictions=study['evaluation']['predictions']
    methods=sorted({p['method'] for p in predictions})
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for method in methods:
        selected=[p for p in predictions if p['method']==method and p['status']=='ok' and p['domain']=='shape']
        if selected:
            errors=[np.abs(p['estimate']-p['truth']).sum() for p in selected]
            axes[0].scatter([method]*len(errors),errors,s=8,alpha=.5)
            axes[1].plot(np.mean([p['estimate']-p['truth'] for p in selected],axis=0),label=method)
    axes[0].set(ylabel='Shape L1 error (unit integral)',title='Outer hold-outs; see coverage denominators')
    axes[0].tick_params(axis='x',rotation=30)
    axes[1].set(xlabel='Strip index (0-based)',ylabel='Mean shape residual')
    if axes[1].lines:axes[1].legend()
    fig.tight_layout();fig.savefig(plots/'holdout_diagnostics.png');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4))
    for method in methods:
        selected=[p for p in predictions if p['method']==method and p['status']=='ok' and p['domain']=='absolute' and p['truth'].sum()>0]
        if selected:
            axes[0].scatter([method]*len(selected),[(p['estimate'].sum()/p['truth'].sum()-1) for p in selected],s=10)
        shape=study['metrics']['metrics'].get(method,{}).get('shape',{})
        for level in (68,95):
            value=shape.get(f'coverage{level}')
            if value is not None:axes[1].scatter(method,value,label=f'{method} {level}%')
    axes[0].set(ylabel='Relative integral error',title='Independent exposure required')
    axes[1].axhline(.68,color='gray',linestyle='--');axes[1].axhline(.95,color='gray',linestyle=':')
    axes[1].set(ylabel='Marginal strip coverage',ylim=(0,1),title='Exploratory intervals, held-out truth')
    for ax in axes:ax.tick_params(axis='x',rotation=30)
    fig.tight_layout();fig.savefig(plots/'integral_coverage.png');plt.close(fig)
    neighbors=[]
    for key,row in audit['metadata'].items():
        if str(row.get('experiment_group','')).casefold()!='vinci':continue
        run,state=key
        fig,axes=plt.subplots(1,2,figsize=(10,4))
        for donor in ((run-1,state),key,(run+1,state)):
            ok=donor in audit['histograms'] and donor in audit['metadata'] and compatible(row,audit['metadata'][donor])
            neighbors.append(dict(target=key,neighbor=donor,compatible=ok))
            if ok:
                values=audit['histograms'][donor]
                axes[0].plot(values,label=str(donor[0]));axes[1].plot(values/values.sum(),label=str(donor[0]))
        axes[0].set(title='Measured contents',xlabel='Strip',ylabel='Flux content')
        axes[1].set(title='Measured shapes',xlabel='Strip',ylabel='Unit integral')
        for ax in axes:
            if ax.lines:ax.legend()
        fig.tight_layout();fig.savefig(plots/f'vinci_{run}_{state}.png');plt.close(fig)
    write_json(directory/'vinci_neighbors.json',neighbors)


def write_study(directory, audit, study):
    directory=Path(directory)
    summary={k:v for k,v in study.items() if k not in ('evaluation','uncertainty','candidate_uncertainty','candidates')}
    summary['candidates']=[_public_prediction(row) for row in study['candidates']]
    if 'evaluation' in study:
        summary['split_manifest']=study['evaluation']['folds']
        summary['excluded']=study['evaluation']['excluded']
    summary['inputs']=audit['inputs']
    write_json(directory/'study.json',summary)
    if 'evaluation' not in study:return
    predictions=study['evaluation']['predictions']
    write_csv(directory/'validation.csv',[_public_prediction(row) for row in predictions])
    provenance=dict(schema_version=1,mode=study['mode'],seed=study['seed'],status=study['status'],
                    inputs=audit['inputs'],synthetic_is_not_measurement=True,
                    interval_kind=study['uncertainty']['interval_kind'])
    _root_records(directory/'study.root',predictions,study['uncertainty'],provenance,'holdout')
    if study['candidates']:
        _root_records(directory/'synthetic_flux.root',study['candidates'],study['candidate_uncertainty'],provenance,'synthetic')
    _study_plots(directory,audit,study)
