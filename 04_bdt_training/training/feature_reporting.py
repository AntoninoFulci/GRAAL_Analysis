"""Auditable ROOT/PDF distributions of validated Stage-1 feature datasets.

No model import, fitting, reweighting or random split. ROOT and PDF share one
histogram representation so the rendered plots have exactly the saved yields.
"""
from __future__ import annotations

from array import array
from dataclasses import asdict, dataclass
import hashlib
import importlib
import json
from pathlib import Path
import platform
import subprocess
from tempfile import TemporaryDirectory
import textwrap

import numpy as np

from bdt_training.dataset.stage1_dataset import load_stage1_dataset
from bdt_training.dataset.grouped_split import audit_group_splits
from graal_common.physics.channels import HYPOTHESES, M_PROTON
from graal_common.stage1.feature_descriptions import FeatureDefinition, feature_definitions


@dataclass(frozen=True)
class FeatureHistogram:
    edges: np.ndarray
    sumw: np.ndarray  # ROOT convention: underflow, normal bins, overflow
    sumw2: np.ndarray
    entries: int  # finite feature entries, including zero-weight events and flows
    stats: tuple[float, float, float, float]  # normal-bin ROOT statistics
    audit: dict

    @property
    def normalization(self) -> float | None:
        total = float(self.sumw.sum())
        return 1. / total if total > 0 else None


@dataclass(frozen=True)
class FeatureReport:
    definitions: tuple[FeatureDefinition, ...]
    histograms: dict
    metadata: dict


def _sha256(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else _hash_stream(stream)


def _hash_stream(stream) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def _totals(weights: np.ndarray) -> dict:
    return {'entries': len(weights), 'sumw': float(weights.sum()),
            'sumw2': float(np.dot(weights, weights))}


def _histogram(values: np.ndarray, weights: np.ndarray, edges: np.ndarray) -> FeatureHistogram:
    finite = np.isfinite(values)
    x, w = values[finite], weights[finite]
    bins = np.searchsorted(edges, x, side='right')
    sumw = np.bincount(bins, weights=w, minlength=len(edges) + 1)
    sumw2 = np.bincount(bins, weights=w*w, minlength=len(edges) + 1)
    regular = (bins > 0) & (bins < len(edges))
    r, rw = x[regular], w[regular]
    stats = (float(rw.sum()), float(np.dot(rw, rw)),
             float(np.dot(rw, r)), float(np.dot(rw, r*r)))
    audit = {
        'total': _totals(weights), 'finite': _totals(w),
        'nan': _totals(weights[~finite]),
        'underflow': _totals(w[bins == 0]),
        'overflow': _totals(w[bins == len(edges)]),
        'normalization': 'unit sum including flows; NaN excluded' if sumw.sum() > 0
                         else 'undefined: non-positive finite sum of weights',
        'shape_scale': float(1. / sumw.sum()) if sumw.sum() > 0 else None,
    }
    if not np.isfinite(np.concatenate((sumw, sumw2, stats))).all():
        raise ValueError('histogram sums overflow float64')
    return FeatureHistogram(edges, sumw, sumw2, len(x), stats, audit)


def _row_provenance(rows) -> dict:
    if rows is None:
        return {
            'split_status': 'unavailable; full dataset only',
            'channel_status': 'unavailable; binary classes only',
            'photon_loss': None,
            'photon_loss_status': 'not persisted in Stage1Dataset; current defaults are not provenance',
            'model_binding': 'not verified; NPZ has no model hash or persisted split indices',
        }
    split_audit = None
    split_status = 'not persisted; full dataset histograms only'
    if rows.split is not None:
        split_audit = audit_group_splits(rows.origin_id, rows.split)
        split_status = 'persisted and audited; full dataset histograms only'
    return {
        'split_status': split_status,
        'split_audit': split_audit,
        'channel_status': 'persisted per row; full dataset histograms only',
        'channels': np.unique(rows.channel).tolist(),
        'detector_variants': np.unique(rows.detector_variant).tolist(),
        'photon_loss': None,
        'photon_loss_status': 'detector variants persisted verbatim; parameters not inferred',
        'model_binding': 'not verified; NPZ has no model hash',
    }


def build_feature_report(feature_paths, *, training_seed: int | None = None) -> FeatureReport:
    """Validate inputs and summarize full datasets, keeping profiles separate.

    Legacy NPZs do not record splits, channel IDs or photon-loss configuration.
    Record these as unavailable, even if today's builder has defaults for them.
    """
    if not feature_paths:
        raise ValueError('at least one feature NPZ is required')
    histograms, inputs, audits = {}, [], {}
    definitions, hypothesis_name = None, None
    for filename in feature_paths:
        path = Path(filename).resolve()
        before = path.stat()
        fingerprint = _sha256(path)
        dataset = load_stage1_dataset(path)
        if _sha256(path) != fingerprint:
            raise ValueError(f'input changed while reading: {path}')
        meta = dataset.metadata
        hypothesis = HYPOTHESES[meta.hypothesis]
        current_definitions = feature_definitions(hypothesis)
        if meta.feature_names != tuple(s.name for s in current_definitions):
            raise ValueError(f'{path}: feature names/order does not match hypothesis contract')
        if hypothesis_name is not None and hypothesis_name != meta.hypothesis:
            raise ValueError('cannot compare different hypothesis schemas in one report')
        definitions, hypothesis_name = current_definitions, meta.hypothesis
        profile = meta.beam_profile or 'unknown'
        if profile in histograms:
            raise ValueError(f'duplicate beam profile {profile!r}; export datasets separately')
        if dataset.X.dtype.kind not in 'fiu' or dataset.w.dtype.kind not in 'fiu':
            raise ValueError('features and weights must be real numeric arrays')
        if np.isinf(dataset.X).any():
            raise ValueError(f'{path}: infinite features are invalid; NaN is counted separately')
        for i, spec in enumerate(definitions):
            column = dataset.X[:, i]
            finite = column[np.isfinite(column)]
            if spec.kind == 'discrete' and np.any(finite != np.floor(finite)):
                raise ValueError(f'{spec.name} must contain integer counts or NaN')
        histograms[profile] = {}
        for label, value in (('signal', 1), ('background', 0)):
            selected = dataset.y == value
            weights = dataset.w[selected].astype(np.float64)
            unit_weights = np.ones(len(weights), dtype=np.float64)
            feature_histograms = []
            for i, spec in enumerate(definitions):
                values = dataset.X[selected, i].astype(np.float64)
                pair = {mode: _histogram(values, w, np.asarray(spec.edges))
                        for mode, w in (('weighted', weights), ('unweighted', unit_weights))}
                feature_histograms.append(pair)
                audits[f'{profile}/all/{label}/{spec.name}'] = {
                    mode: h.audit for mode, h in pair.items()}
            histograms[profile][label] = feature_histograms
        inputs.append({
            'path': str(path), 'bytes': before.st_size, 'sha256': fingerprint,
            'shape': list(dataset.X.shape),
            'array_dtypes': {k: str(getattr(dataset, k).dtype) for k in ('X', 'y', 'w')},
            **asdict(meta),
            'class_totals': {label: _totals(dataset.w[dataset.y == value].astype(np.float64))
                             for label, value in (('signal', 1), ('background', 0))},
            'training_seed': training_seed,
            **_row_provenance(dataset.rows),
        })
    repo = Path(__file__).resolve().parents[2]
    code_revision = None
    if (repo / '.git').exists():
        try:
            revision = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'],
                                      capture_output=True, text=True, check=False)
            if revision.returncode == 0:
                code_revision = revision.stdout.strip()
        except OSError:
            pass  # Git is not a runtime dependency; source hashes remain available.
    source_modules = ('graal_common.stage1.features',
                      'graal_common.stage1.feature_descriptions',
                      'graal_common.physics.pairing', 'graal_common.physics.channels',
                      'bdt_training.dataset.stage1_dataset', __name__)
    metadata = {
        'schema_version': 1, 'inputs': inputs,
        'features': [asdict(s) for s in definitions],
        'histograms': audits,
        'hypothesis': asdict(HYPOTHESES[hypothesis_name]), 'target_mass_gev': M_PROTON,
        'definition_basis': 'current shared feature contract; historical formula version not persisted in NPZ',
        'selection': 'all NPZ rows; no additional cuts, reweighting or resplitting',
        'binning': 'fixed common windows independent of all input rows; ROOT under/overflow retained',
        'units': 'natural units c=1; GeV for energy, mass and momentum; 1 means dimensionless',
        'shape': 'separate clone divided by finite sumw including flows; not bin-width density; '
                 'absent if sumw <= 0; error=sqrt(sumw2)/sumw (fixed normalization)',
        'nan_policy': 'omit from TH1, retain entries/sumw/sumw2 per feature in this metadata',
        'root_entries': 'finite feature values, including zero-weight events and flows',
        'code_revision': code_revision,
        'source_sha256': {name: _sha256(Path(importlib.import_module(name).__file__))
                          for name in source_modules},
        'versions': {'python': platform.python_version(), 'numpy': np.__version__},
    }
    # Reject non-finite optional metadata too, before any file is published.
    json.dumps(metadata, allow_nan=False)
    return FeatureReport(definitions, histograms, metadata)


def _write_root(report: FeatureReport, destination: Path, ROOT) -> None:
    root = ROOT.TFile.Open(str(destination), 'RECREATE')
    if not root or root.IsZombie():
        raise OSError(f'cannot create ROOT file: {destination}')
    try:
        ROOT.TNamed('training_features_metadata', json.dumps(report.metadata, allow_nan=False)).Write()
        for profile, classes in report.histograms.items():
            directory = root.mkdir(profile).mkdir('all')
            for label, features in classes.items():
                class_dir = directory.mkdir(label)
                for spec, pair in zip(report.definitions, features, strict=True):
                    feature_dir = class_dir.mkdir(spec.name)
                    feature_dir.cd()
                    for mode, source in pair.items():
                        title = f'{profile} {label}: {spec.name};{spec.name} [{spec.unit}];'
                        h = ROOT.TH1D(f'{mode}_yield', title + 'sum(w)' if mode == 'weighted'
                                      else title + 'events', len(source.edges) - 1,
                                      array('d', source.edges))
                        h.SetDirectory(0)
                        h.Sumw2()
                        for i, (value, variance) in enumerate(zip(source.sumw, source.sumw2, strict=True)):
                            h.SetBinContent(i, float(value))
                            h.SetBinError(i, float(np.sqrt(variance)))
                        h.PutStats(array('d', source.stats))
                        h.SetEntries(source.entries)
                        if h.Write() <= 0:
                            raise OSError(f'failed writing histogram {spec.name}')
                        if source.normalization is not None:
                            shape = h.Clone(f'{mode}_shape')
                            shape.SetDirectory(0)
                            shape.Scale(source.normalization)
                            shape.GetYaxis().SetTitle('fraction per bin (including flows)')
                            if shape.Write() <= 0:
                                raise OSError(f'failed writing shape {spec.name}')
        root.Flush()
        if root.TestBit(ROOT.TFile.kWriteError):
            raise OSError(f'ROOT write error: {destination}')
    finally:
        root.Close()


def _write_pdf(report: FeatureReport, destination: Path) -> None:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    with PdfPages(destination) as pdf:
        fig = plt.figure(figsize=(11.7, 8.3))
        summary = ['Stage-1 training feature distributions', '',
                   'All stored rows. Weighted yields are training weights, not measured cross sections.',
                   'No new split, training, cut or reweighting. UV/VIS remain separate.',
                   'Common fixed windows. Flows and NaN shown explicitly on each feature page.',
                   'Shape = bin fraction, normalized INCLUDING flows (NaN excluded).',
                   'Errors: sqrt(sum(w^2)); shape errors treat normalization as fixed.',
                   'Histograms include all rows; stored channel/split provenance is summarized in JSON.',
                   'Missing photon-loss settings and training seeds are not guessed.', '']
        for item in report.metadata['inputs']:
            summary.extend(textwrap.wrap(item['path'], 110))
            summary.extend([f"  profile={item['beam_profile'] or 'unknown'}; rows={item['shape'][0]:,}; "
                            f"hypothesis={item['hypothesis']}; prior={item['signal_prior']}",
                            f"  SHA256: {item['sha256']}", ''])
        summary += ['Definitions follow the current shared contract (c=1).',
                    'Historical feature formula version / association with a model: not verified.',
                    'Full dictionary, bin edges, hashes and audit counts are embedded in ROOT',
                    'and repeated in training_features.json.']
        fig.text(.06, .94, '\n'.join(summary), va='top', fontsize=10, linespacing=1.55)
        pdf.savefig(fig)
        plt.close(fig)
        colors = {'signal': '#1675ad', 'background': '#d56625'}
        page = 1
        for profile, classes in report.histograms.items():
            for i, spec in enumerate(report.definitions):
                fig, axes = plt.subplots(2, 2, figsize=(11.7, 8.3))
                notes = []
                for row, mode in enumerate(('weighted', 'unweighted')):
                    for label, features in classes.items():
                        h = features[i][mode]
                        centers = (h.edges[:-1] + h.edges[1:]) / 2
                        for col, scale in enumerate((1., h.normalization)):
                            ax = axes[row, col]
                            if scale is None:
                                ax.text(.04, .9 if label == 'signal' else .82,
                                        f'{label}: undefined shape (sumw <= 0)',
                                        transform=ax.transAxes, fontsize=8)
                                continue
                            y = h.sumw[1:-1] * scale
                            ax.stairs(y, h.edges, color=colors[label], label=label)
                            ax.errorbar(centers, y, yerr=np.sqrt(h.sumw2[1:-1])*scale,
                                        fmt='none', color=colors[label], alpha=.5, linewidth=.6)
                            if np.all(h.sumw >= 0):
                                # Symlog preserves empty bins and weighted tails.
                                ax.set_yscale('symlog', linthresh=max(np.max(np.abs(y))*.001, 1e-8))
                        a = h.audit
                        notes.append(f"{mode:10s} {label:10s} N={a['total']['entries']:>8,d}  "
                                     f"sumw={a['total']['sumw']:.6g}  "
                                     f"UF={a['underflow']['sumw']:.6g}  OF={a['overflow']['sumw']:.6g}  "
                                     f"NaN={a['nan']['entries']} (w={a['nan']['sumw']:.6g})")
                    for col in range(2):
                        ax = axes[row, col]
                        ax.set_title(f"{mode.capitalize()} {'yield' if col == 0 else 'shape'}", fontsize=11)
                        ax.set_xlabel(f'{spec.name} [{spec.unit}]', fontsize=9)
                        ax.set_ylabel('sum(w)' if col == 0 and mode == 'weighted' else
                                      'events' if col == 0 else 'fraction / bin')
                        ax.grid(alpha=.2)
                        ax.legend(fontsize=8)
                        if i == 8:
                            ax.set_xscale('symlog', linthresh=.01)
                fig.suptitle(f'{profile.upper()} | {spec.name}', fontsize=15, y=.97)
                fig.text(.07, .91, '\n'.join(textwrap.wrap(spec.formula, 125)), fontsize=8, va='top')
                fig.text(.07, .04, '\n'.join(notes), fontsize=8, family='monospace', linespacing=1.5)
                fig.text(.96, .02, str(page + 1), ha='right', fontsize=8)
                fig.subplots_adjust(top=.80, bottom=.24, hspace=.58, wspace=.28, left=.08, right=.97)
                pdf.savefig(fig)
                plt.close(fig)
                page += 1


def export_training_features(feature_paths, out_dir, *, training_seed: int | None = None) -> dict:
    """Publish ROOT, PDF and JSON into a separate diagnostic directory.

    Refuse replacement of existing evidence. Stage all outputs before publishing
    so a rendering/ROOT failure cannot leave an apparently complete report.
    """
    out = Path(out_dir)
    names = ('training_features.root', 'training_features.pdf', 'training_features.json')
    for name in names:
        if (out / name).exists():
            raise FileExistsError(f'diagnostic artifact already exists: {out / name}')
    report = build_feature_report(feature_paths, training_seed=training_seed)
    import ROOT
    import matplotlib
    report.metadata['versions'].update(ROOT=ROOT.gROOT.GetVersion(), matplotlib=matplotlib.__version__)
    out.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.training-features-', dir=out) as temporary:
        stage = Path(temporary)
        _write_root(report, stage / names[0], ROOT)
        _write_pdf(report, stage / names[1])
        (stage / names[2]).write_text(json.dumps(report.metadata, indent=2, allow_nan=False) + '\n')
        # Hard links publish complete files without overwriting a concurrent writer.
        published = []
        try:
            for name in names:
                target = out / name
                target.hardlink_to(stage / name)
                published.append(target)
        except OSError:
            for target in published:
                target.unlink()
            raise
    return report.metadata
