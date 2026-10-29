"""Read-only preflight and protected execution of an explicit stage campaign."""
from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
import importlib
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from calibration.common_inputs import load_common_inputs
from . import artifact_manifest as cache
from . import logging as console
from .execution import execute_cached_plan, _stage_sources
from .models import ArtifactGroup, PipelineError, Stage, flatten_stages
from .paths import (pipeline_lock, prepare_output_dirs, validate_test_output,
                    validate_production_output, _replace_test_output, _writable_ancestor)
from .publication import organize_campaign_reports
from .resources import bounded_runner
from .stage_configuration import StageConfiguration, PROFILE_STAGES, COMMON_STAGES
from .stage_inputs import validate_product
from .stage_planning import CampaignPlan, build_stage_plan


def _json(value):
    return json.loads(json.dumps(value, default=str, allow_nan=False))


def _leaves(value, prefix=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, f'{prefix}.{key}' if prefix else str(key))
    else:
        yield prefix, value


def effective_configuration(plan: CampaignPlan) -> dict:
    data = deepcopy(plan.configuration.data)
    data['campaign']['repo_root'] = plan.paths.repo_root
    data['campaign']['output_dir'] = plan.paths.output_root
    return _json(data)


def _change_action(key: str) -> str:
    if key.startswith('profiles.') and key.endswith('.energy_edges_gev'):
        return 'revalidate upstream energy coverage and rebuild extraction'
    if key.startswith('stages.reconstruction.') and key.rsplit('.', 1)[-1] in ('chi2_cut', 'missing_mass_window_gev'):
        return 'require compatible reconstruction and rebuild downstream'
    if key.startswith('stages.extraction.'):
        return 'rebuild extraction and comparison; selection, MC and BDT are not invalidated by this setting alone'
    return 'use requested settings in a new campaign; validate compatibility of reused products'


def _differences(requested, recorded, prefix='') -> list[str]:
    current = dict(_leaves(_json(requested), prefix))
    previous = dict(_leaves(_json(recorded), prefix))
    return [f'{key}: recorded={previous.get(key, "<absent>")!r}; requested={current.get(key, "<absent>")!r}; '
            f'action={_change_action(key)}'
            for key in sorted(set(current) | set(previous)) if current.get(key) != previous.get(key)]


def compare_configurations(current: dict, reference: Path) -> list[str]:
    path = Path(reference) / 'metadata/effective_configuration.json'
    try:
        previous = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(previous, dict) or previous.get('schema_version') != 1
                or any(not isinstance(previous.get(key), dict)
                       for key in ('campaign', 'execution', 'inputs', 'profiles', 'stages'))):
            raise ValueError('missing structured effective configuration schema')
    except (OSError, ValueError, UnicodeError) as exc:
        raise PipelineError(f'campaign.compare_to: cannot read {path}: {exc}') from exc
    return _differences(current, previous)


def _product_paths(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _product_paths(child)
    elif value is not None:
        yield Path(value)


def _entry_name(entry):
    return entry.stages[0].name if isinstance(entry, ArtifactGroup) else entry.name


def _overlap(first: Path, second: Path) -> bool:
    first, second = first.resolve(), second.resolve()
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _write_targets(plan):
    yield plan.paths.output_root
    for entry in plan.entries:
        if isinstance(entry, ArtifactGroup):
            yield entry.destination
            if plan.mode.name == 'production':
                yield (entry.destination.with_suffix('.manifest.json') if entry.kind == 'mc'
                       else entry.destination.parent / f'{entry.profile}.manifest.json')
    for stage in flatten_stages(plan.entries):
        for option, value in zip(stage.argv, stage.argv[1:]):
            if option in ('--output-dir', '--out-dir', '--cache-root', '--feature-diagnostics-dir'):
                path = Path(value)
                yield path if path.is_absolute() else plan.paths.repo_root / path
    if plan.configuration.data['stages']['calibration']['enabled']:
        yield plan.paths.artifact_root / '06_calibration'


def validate_output_safety(plan: CampaignPlan) -> None:
    """Protect every declared input, including unused bindings and path aliases."""
    data = plan.configuration.data
    (validate_test_output if plan.mode.name == 'test_data' else validate_production_output)(plan.paths)
    if plan.mode.name == 'production' and _overlap(plan.paths.output_root, plan.paths.artifact_root):
        raise PipelineError('production campaign output must not overlap the reserved managed cache')
    protected = [(f'inputs.{key}', Path(value)) for key, value in _leaves(data['inputs']) if value is not None]
    if plan.configuration.source is not None:
        protected.append(('source YAML', plan.configuration.source))
    for key in ('compare_to',):
        if data['campaign'][key] is not None:
            protected.append((f'campaign.{key}', data['campaign'][key]))
    for name, field in (('preanalysis', 'cuts_dir'), ('calibration', 'common_inputs'),
                        ('flux_study', 'metadata'), ('comparison', 'published_reference')):
        value = data['stages'][name][field]
        if value is not None:
            protected.append((f'stages.{name}.{field}', value))
    for profile in ('uv', 'vis'):
        value = data['stages']['bdt'][profile]['hyperparams']
        if value is not None:
            protected.append((f'stages.bdt.{profile}.hyperparams', value))
    planned_stages = flatten_stages(plan.entries)
    kinds = {stage.kind for stage in planned_stages}
    if kinds & {'calibrate_flux', 'extract', 'flux_audit', 'flux_study'}:
        protected.extend((name, value) for name, value in (
            ('resolved run catalog', plan.paths.manifest), ('resolved raw flux', plan.paths.raw_flux),
            ('resolved run quality', plan.paths.quality_path)))
    for stage in planned_stages:
        for option, value in zip(stage.argv, stage.argv[1:]):
            if option in ('--hyperparams', '--published-csv', '--run-metadata', '--manifest', '--run-manifest', '--run-quality'):
                path = Path(value)
                protected.append((f'{stage.name} {option}', path if path.is_absolute() else plan.paths.repo_root / path))
    if 'preanalysis' in kinds:
        protected.append(('detector cuts', data['stages']['preanalysis']['cuts_dir']
                          or plan.paths.repo_root / '01_pre_analysis/cuts'))
    # Always preserve the immutable diagnostic cohort, regardless of consumption.
    protected.append(('immutable UV+VIS cohort', plan.paths.repo_root / 'data_test/sample'))
    targets = tuple(set(path.absolute() for path in _write_targets(plan)))
    for destination in targets:
        for name, source in protected:
            if _overlap(destination, source):
                raise PipelineError(f'output/input overlap: {destination} would modify {name} ({source})')
    managed_cache = plan.paths.artifact_root
    if any(isinstance(entry, ArtifactGroup) for entry in plan.entries) or data['stages']['calibration']['enabled']:
        if managed_cache.is_symlink():
            raise PipelineError(f'managed cache root must not be a symlink: {managed_cache}')
        for destination in targets:
            if destination.is_relative_to(managed_cache):
                current = destination
                while current != managed_cache:
                    if current.is_symlink():
                        raise PipelineError(f'managed cache path must not be a symlink: {current}')
                    current = current.parent
    for stage in flatten_stages(plan.entries):
        if stage.kind in ('flux_audit', 'flux_study'):
            destination = Path(stage.argv[stage.argv.index('--output-dir') + 1])
            current = destination
            while current != plan.paths.repo_root and current != current.parent:
                if current.is_symlink():
                    raise PipelineError(f'flux diagnostic output must not contain symlinks: {current}')
                current = current.parent
            if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
                raise PipelineError(f'flux diagnostic output is not empty: {destination}')
    for destination in targets:
        ancestor = _writable_ancestor(destination.parent if destination.is_file() else destination)
        if not ancestor.is_dir() or not os.access(ancestor, os.W_OK):
            raise PipelineError(f'output parent is not writable: {ancestor}')
    preanalysis = data['stages']['preanalysis']
    if preanalysis['enabled']:
        target = preanalysis['output_dir']
        if target is None or target.exists() or target.is_symlink():
            raise PipelineError(f'stages.preanalysis.output_dir must be a new directory: {target}')
        # A fresh h80 subdirectory may belong to the campaign, but cannot share
        # a destination with another producer or directories created at claim time.
        claimed = (plan.paths.output_root, plan.paths.command_log.parent,
                   plan.paths.calibrated_flux.parent,
                   plan.paths.profile_root('uv') / 'reco', plan.paths.profile_root('vis') / 'reco')
        if any(path.resolve().is_relative_to(target.resolve()) for path in claimed):
            raise PipelineError('stages.preanalysis.output_dir overlaps directories reserved by the campaign')
        others = [path for path in targets if path.resolve() not in (target.resolve(), plan.paths.output_root.resolve())]
        for stage in planned_stages:
            if stage.kind != 'preanalysis':
                for option, value in zip(stage.argv, stage.argv[1:]):
                    if option in ('--output-dir', '--out-dir', '--cache-root', '--feature-diagnostics-dir'):
                        path = Path(value)
                        others.append(path if path.is_absolute() else plan.paths.repo_root / path)
        if _overlap(target, plan.paths.artifact_root) or any(_overlap(target, path) for path in others):
            raise PipelineError('stages.preanalysis.output_dir overlaps another generated product or managed cache')


def _runtime_modules(kinds: set[str]) -> set[str]:
    modules = set()
    for kind in kinds:
        if kind in ('preanalysis', 'select', 'reconstruct_chi2', 'reconstruct_bdt',
                    'extract', 'plots', 'reconstruction_plots', 'comparison', 'calibrate_flux',
                    'flux_audit', 'flux_study'):
            modules.add('ROOT')
        if kind not in ('generate', 'command'):
            modules.update(('numpy', 'uproot'))
        if kind in ('features', 'beam_spectrum', 'reconstruct_chi2', 'reconstruct_bdt', 'extract'):
            modules.add('awkward')
        if kind in ('train', 'reconstruct_bdt'):
            modules.add('xgboost')
        if kind == 'train':
            modules.add('sklearn')
        if kind in ('extract', 'plots', 'reconstruction_plots', 'comparison', 'calibrate_flux', 'flux_audit', 'flux_study', 'mc_status'):
            modules.add('matplotlib')
        if kind in ('extract', 'comparison'):
            modules.add('scipy')
    return modules


def _validate_raw(plan):
    data = plan.configuration.data
    raw = data['inputs']['raw_dir']
    cuts = data['stages']['preanalysis']['cuts_dir'] or plan.paths.repo_root / '01_pre_analysis/cuts'
    if raw is None or not raw.is_dir():
        raise PipelineError(f'inputs.raw_dir: raw directory not found: {raw}')
    if not cuts.is_dir() or not tuple(cuts.glob('*.cpp')):
        raise PipelineError(f'stages.preanalysis.cuts_dir: detector cuts not found: {cuts}')
    files = sorted(raw.glob('*/*.root'))
    if not files:
        raise PipelineError(f'inputs.raw_dir: no h70 files under acquisition subdirectories: {raw}')
    try:
        for path in files:
            cache.validate_root(path, 'h70', (), nonempty=False)
    except Exception as exc:
        raise PipelineError(f'inputs.raw_dir: invalid h70 input: {exc}') from exc
    for name in ('PreAnalysis.C', 'PreAnalysis.h', 'RawTrackContract.h', 'CutManager.h'):
        path = plan.paths.repo_root / '01_pre_analysis' / name
        if not path.is_file():
            raise PipelineError(f'preanalysis source not found: {path}')


def _required_keys(plan):
    return {key for keys in plan.requirements.values() for key in keys}


def _unused_input_warnings(plan):
    used = _required_keys(plan)
    warnings = []
    for key, product in plan.products.items():
        if product.producer is None and key not in used:
            warnings.append(f'inputs.{key}: explicit input is unused by this plan; action=leave untouched')
    if plan.configuration.data['inputs']['raw_dir'] is not None and not plan.configuration.data['stages']['preanalysis']['enabled']:
        warnings.append('inputs.raw_dir: explicit input is unused by this plan; action=leave untouched')
    return warnings


def preflight_stage_plan(plan: CampaignPlan, *, import_module=importlib.import_module,
                         which=shutil.which) -> list[str]:
    """Validate only resources and external dependencies consumed by this plan."""
    if sys.version_info < (3, 10):
        raise PipelineError('Python 3.10 or newer is required')
    stages = flatten_stages(plan.entries)
    kinds = {stage.kind for stage in stages}
    runtime_modules = _runtime_modules(kinds)
    if any(stage.kind == 'train' and '--feature-diagnostics-dir' in stage.argv for stage in stages):
        runtime_modules.add('ROOT')
    for name in sorted(runtime_modules):
        try:
            import_module(name)
        except Exception as exc:
            raise PipelineError(f'cannot import {name} for requested stages: {exc}') from exc
    if kinds & {'generate', 'preanalysis'} and which('root') is None:
        raise PipelineError('root executable not found on PATH for requested native stages')
    for stage in stages:
        if '-m' in stage.argv:
            module_name = stage.argv[stage.argv.index('-m') + 1]
            try:
                if importlib.util.find_spec(module_name) is None:
                    raise ImportError(f'no module named {module_name}')
            except (ImportError, ValueError, AttributeError) as exc:
                raise PipelineError(f'{stage.name}: stage module unavailable: {exc}') from exc
        for arg in stage.argv:
            if arg.endswith('.py') and Path(arg).is_absolute() and not Path(arg).is_file():
                raise PipelineError(f'required stage driver not found: {arg}')
            if '.C(' in arg:
                macro = Path(arg.split('.C(', 1)[0] + '.C')
                if not macro.is_file():
                    raise PipelineError(f'required generator source not found: {macro}')
                for header in ('smearing.h', 'beam_window.h', 'generator_runtime.h'):
                    if not (macro.parent / header).is_file():
                        raise PipelineError(f'required generator header not found: {macro.parent / header}')
        for option, value in zip(stage.argv, stage.argv[1:]):
            if option in ('--hyperparams', '--published-csv', '--run-metadata') and not Path(value).is_file():
                raise PipelineError(f'{stage.name}: {option} file not found: {value}')
    if kinds & {'calibrate_flux', 'extract', 'flux_audit', 'flux_study'}:
        try:
            common = load_common_inputs(plan.paths.repo_root,
                                       path=plan.configuration.data['stages']['calibration']['common_inputs'],
                                       cache=plan.paths.artifact_root)
            expected = {'run_catalog': plan.paths.manifest.resolve(),
                        'run_quality': plan.paths.quality_path.resolve(), 'raw_flux': plan.paths.raw_flux.resolve()}
            if common['inputs'] != expected:
                raise ValueError('planned common inputs differ from verified manifest')
        except (ValueError, OSError) as exc:
            raise PipelineError(f'invalid common inputs: {exc}') from exc
    if 'preanalysis' in kinds:
        _validate_raw(plan)
    metadata = plan.configuration.data['stages']['flux_study']['metadata']
    if kinds & {'flux_audit', 'flux_study'} and metadata is not None:
        from calibration.run_manifest import validate_manifest
        from flux_studies.metadata import load_metadata
        try:
            load_metadata(metadata, validate_manifest(plan.paths.manifest))
        except (ValueError, OSError) as exc:
            raise PipelineError(f'invalid flux study metadata: {exc}') from exc
    warnings = _unused_input_warnings(plan)
    validated = set()
    for entry in plan.entries:
        stage = entry.stages[0] if isinstance(entry, ArtifactGroup) else entry
        for key in plan.requirements.get(_entry_name(entry), ()):
            product = plan.products[key]
            profile = stage.profile if product.kind == 'preanalysis' and stage.kind == 'select' else product.profile
            identity = (key, profile)
            if product.producer is None and identity not in validated:
                warnings.extend(validate_product(product.kind, product.value, profile=profile,
                                                  config=plan.configuration.data, paths=plan.paths))
                validated.add(identity)
    return warnings


def dependency_gate(plan: CampaignPlan, warnings: list[str], external_identities: dict | None = None):
    """Validate freshly generated dependencies immediately before each consumer."""
    def before_entry(entry):
        stage = entry.stages[0] if isinstance(entry, ArtifactGroup) else entry
        for key in plan.requirements.get(_entry_name(entry), ()):
            product = plan.products[key]
            if product.producer is None and external_identities is not None:
                try:
                    unchanged = cache.inventory(tuple(_product_paths(product.value))) == external_identities[key]
                except (OSError, ValueError) as exc:
                    raise PipelineError(f'inputs.{key}: external product unavailable before consumption: {exc}') from exc
                if not unchanged:
                    raise PipelineError(f'inputs.{key}: external product changed before consumption')
            profile = stage.profile if product.kind == 'preanalysis' and stage.kind == 'select' else product.profile
            for message in validate_product(product.kind, product.value, profile=profile,
                                            config=plan.configuration.data, paths=plan.paths):
                if message not in warnings:
                    warnings.append(message)
                    console.emit(message, 'warning')
    return before_entry


def preview_plan(plan: CampaignPlan) -> list[dict]:
    """Preview cache decisions only when all upstream identities already exist."""
    from .execution import artifact_cache_item
    records = []
    for entry in plan.entries:
        name = _entry_name(entry)
        dependencies = plan.requirements.get(name, ())
        record = {'name': name, 'action': 'RUN', 'reason': 'enabled campaign stage',
                  'dependencies': list(dependencies)}
        if isinstance(entry, ArtifactGroup):
            if plan.mode.name == 'test_data':
                record['reason'] = 'test_data always rebuilds'
            elif entry.force:
                record['reason'] = 'explicit force=true'
            elif any(plan.products[key].producer is not None for key in dependencies):
                record.update(action='PENDING', reason='cache decision waits for generated upstream validation')
            else:
                try:
                    item, validate = artifact_cache_item(entry, plan.entries, plan.paths)
                    reusable, reason = cache.cache_status(item, lambda: validate(entry.destination))
                    record.update(action='SKIP' if reusable else 'RUN', reason=reason)
                except (ValueError, OSError, PipelineError) as exc:
                    record.update(action='RUN', reason=f'cache unavailable: {exc}')
            record.update(destination=str(entry.destination), force=bool(entry.force))
        records.append(record)
    return records


def _print_summary(plan, records, warnings):
    from .cli import _print_table
    data = plan.configuration.data
    rows = [('Mode', plan.mode.name), ('Output', str(plan.paths.output_root))]
    for name in COMMON_STAGES:
        rows.append((name, 'ON' if data['stages'][name]['enabled'] else 'OFF'))
    for profile in ('uv', 'vis'):
        for name in PROFILE_STAGES:
            enabled = data['profiles'][profile]['enabled'] and data['stages'][name][profile]['enabled']
            rows.append((f'{profile}:{name}', 'ON' if enabled else 'OFF'))
    rows.extend((record['name'], f'{record["action"]}: {record["reason"]}') for record in records)
    for key in sorted(_required_keys(plan)):
        product = plan.products[key]
        rows.append((key, f'{"external read-only" if product.producer is None else product.producer}: {product.value}'))
    _print_table('Stage campaign', rows)
    for warning in warnings:
        console.emit(warning, 'warning')


def _identities(plan, *, generated=False):
    identities = {}
    keys = set(plan.products) if generated else _required_keys(plan)
    for key in sorted(keys):
        product = plan.products[key]
        if (product.producer is not None) != generated:
            continue
        paths = tuple(_product_paths(product.value))
        identities[key] = cache.inventory(paths)
    raw = plan.configuration.data['inputs']['raw_dir']
    if not generated and plan.configuration.data['stages']['preanalysis']['enabled'] and raw:
        identities['raw'] = cache.inventory(sorted(raw.glob('*/*.root')))
    return identities



def _source_identities(paths):
    return [{**item, 'sha256': hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()}
            for item in cache.inventory(paths)]


def _published_identities(plan, identities):
    """Keep byte identities pointed at their final report-publication locations."""
    manifest = plan.paths.output_root / 'metadata/output_layout.json'
    if not manifest.is_file():
        return identities
    relocations = json.loads(manifest.read_text())['relocations']
    mapping = {str((plan.paths.output_root / item['source']).resolve()):
               plan.paths.output_root / item['destination'] for item in relocations}
    for items in identities.values():
        for index, item in enumerate(items):
            if item['path'] in mapping:
                items[index] = {**cache.inventory((mapping[item['path']],))[0], 'produced_path': item['path']}
    return identities

def _write_metadata(plan, records, warnings, inputs, sources, *, outcomes=None, outputs=None):
    metadata = plan.paths.command_log.parent
    documents = {
        'effective_configuration.json': effective_configuration(plan),
        'configuration_overrides.json': plan.configuration.overrides,
        'stage_plan.json': {'entries': records, 'requirements': plan.requirements,
                            'commands': [{'name': s.name, 'argv': s.argv} for s in flatten_stages(plan.entries)]},
        'stage_warnings.json': warnings,
        'stage_artifacts.json': {'schema_version': 1, 'inputs': inputs, 'source_files': sources,
                                 'outcomes': outcomes or [], 'outputs': outputs or {}},
    }
    for name, value in documents.items():
        (metadata / name).write_text(json.dumps(value, indent=2, default=str, allow_nan=False) + '\n', encoding='utf-8')
    if plan.configuration.source is not None:
        (metadata / 'source_configuration.yaml').write_text(plan.configuration.source_text, encoding='utf-8')


def run_stage_configuration(configuration: StageConfiguration, *, repo_root: Path | None = None,
                            assume_yes: bool = False) -> int:
    try:
        plan = build_stage_plan(configuration, repo_root=repo_root)
    except (OSError, ValueError) as exc:
        raise PipelineError(f'cannot build stage plan: {exc}') from exc
    data = configuration.data
    warnings = []
    reference = data['campaign']['compare_to']
    if reference is not None:
        warnings.extend(compare_configurations(effective_configuration(plan), reference))
    # Never adopt or overwrite an occupied production campaign, even if equal.
    if plan.mode.name == 'production' and plan.paths.output_root.exists():
        if not plan.paths.output_root.is_dir():
            raise PipelineError(f'output root is not a directory: {plan.paths.output_root}')
        if any(plan.paths.output_root.iterdir()):
            if (plan.paths.output_root / 'metadata/effective_configuration.json').is_file():
                warnings.extend(compare_configurations(effective_configuration(plan), plan.paths.output_root))
            for warning in warnings:
                console.emit(warning, 'warning')
            raise PipelineError(f'output root is not empty: {plan.paths.output_root}; choose a new campaign directory')
    validate_output_safety(plan)
    warnings.extend(preflight_stage_plan(plan))
    records = preview_plan(plan)
    _print_summary(plan, records, warnings)
    if data['execution']['check_only']:
        return 0
    if not assume_yes:
        from .cli import confirm_run
        if not confirm_run():
            console.emit('Pipeline annullata.', 'warning')
            return 0
    try:
        source_paths = _stage_sources(plan.paths, plan.entries)
        sources = _source_identities(source_paths)
        inputs = _identities(plan)
    except (OSError, ValueError) as exc:
        raise PipelineError(f'cannot record campaign input/source identities: {exc}') from exc
    with pipeline_lock(plan.paths.repo_root, mode=plan.mode.name):
        validate_output_safety(plan)
        publication = _replace_test_output(plan.paths) if plan.mode.name == 'test_data' else nullcontext()
        with publication:
            prepare_output_dirs(plan.paths)
            _write_metadata(plan, records, warnings, inputs, sources)
            outcomes = execute_cached_plan(plan.entries, plan.mode, plan.paths,
                                           cpus=data['execution']['cpus'], runner=bounded_runner,
                                           before_entry=dependency_gate(plan, warnings, inputs), write_legacy_metadata=False)
            for product in plan.products.values():
                if product.producer is not None:
                    warnings.extend(validate_product(product.kind, product.value, profile=product.profile,
                                                      config=data, paths=plan.paths))
            if inputs != _identities(plan):
                raise PipelineError('external inputs changed while executing the campaign')
            if sources != _source_identities(source_paths):
                raise PipelineError('scientific source files changed while executing the campaign')
            outputs = _identities(plan, generated=True)
            organize_campaign_reports(plan.paths.output_root)
            outputs = _published_identities(plan, outputs)
            _write_metadata(plan, records, warnings, inputs, sources, outcomes=outcomes, outputs=outputs)
    console.emit(f'Pipeline complete: {plan.paths.output_root}', 'success')
    return 0
