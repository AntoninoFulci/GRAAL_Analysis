"""Bind explicit stage switches to the existing scientific commands."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import sys

from calibration.common_inputs import load_common_inputs
from graal_common.physics.channels import get_channel
from graal_common.physics.energy_binning import EnergyBinning
from .models import ArtifactGroup, ModeConfig, PipelineError, PipelinePaths, PreflightResult, Stage
from .paths import build_paths, mode_config
from .planning import _argv, _common_stages, _profile_stages
from .resources import configure_resources
from .stage_configuration import StageConfiguration


@dataclass(frozen=True)
class Product:
    kind: str
    profile: str | None
    value: Path | dict
    producer: str | None


@dataclass(frozen=True)
class CampaignPlan:
    configuration: StageConfiguration
    mode: ModeConfig
    paths: PipelinePaths
    entries: tuple[Stage | ArtifactGroup, ...]
    products: dict[str, Product]
    requirements: dict[str, tuple[str, ...]]


def with_options(stage: Stage, **options) -> Stage:
    """Replace complete argparse options, including variable-length values."""
    argv = list(stage.argv)
    for name, value in options.items():
        flag = '--' + name.replace('_', '-')
        if flag in argv:
            start = argv.index(flag)
            end = start + 1
            while end < len(argv) and not argv[end].startswith('--'):
                end += 1
            del argv[start:end]
        if value is False or value is None:
            continue
        argv.append(flag)
        if value is not True:
            argv.extend(str(item) for item in (value if isinstance(value, (tuple, list)) else (value,)))
    return replace(stage, argv=tuple(argv))


def build_stage_plan(configuration: StageConfiguration, *, repo_root: Path | None = None,
                     root_executable: str = 'root', python_executable: str = sys.executable) -> CampaignPlan:
    data = configuration.data
    settings, inputs = data['stages'], data['inputs']
    explicit = repo_root or data['campaign']['repo_root']
    checkout = Path(explicit).expanduser().resolve() if explicit else Path(__file__).resolve().parents[1]
    if explicit is None and any(part in {'site-packages', 'dist-packages'} for part in checkout.parts):
        raise PipelineError('installed workflow requires --repo-root PATH to a GRAAL checkout')
    mode = mode_config(data['campaign']['mode'], checkout)
    preanalysis = settings['preanalysis']['output_dir'] if settings['preanalysis']['enabled'] else inputs['preanalysis_dir']
    needs_common = any(settings[name]['enabled'] for name in ('calibration', 'flux_study')) or any(
        data['profiles'][p]['enabled'] and settings['extraction'][p]['enabled'] for p in ('uv', 'vis'))
    common_path = settings['calibration']['common_inputs']
    try:
        paths = build_paths(replace(mode, preanalysis_dir=preanalysis or mode.preanalysis_dir),
                            data['campaign']['output_dir'], resolve_common=needs_common and common_path is None)
    except (OSError, ValueError) as exc:
        raise PipelineError(f'invalid common inputs: {exc}') from exc
    if common_path and needs_common:
        try:
            common = load_common_inputs(checkout, path=common_path, cache=paths.artifact_root, verify=False)['inputs']
        except (OSError, ValueError) as exc:
            raise PipelineError(f'invalid common inputs: {exc}') from exc
        paths = replace(paths, manifest=common['run_catalog'], run_quality=common['run_quality'], raw_flux=common['raw_flux'])
    products, requirements, entries = {}, {}, []

    def bind(key, kind, profile, external, enabled, generated, producer):
        present = any(v is not None for v in external.values()) if isinstance(external, dict) else external is not None
        if enabled and present:
            raise PipelineError(f'{key}: producer ON conflicts with explicit external input')
        if enabled or present:
            value = generated if enabled else external
            if value is None:
                raise PipelineError(f'{key}: enabled producer requires an explicit output directory')
            products[key] = Product(kind, profile, value, producer if enabled else None)

    def on(name, profile=None):
        return (data['profiles'][profile]['enabled'] and settings[name][profile]['enabled']) if profile else settings[name]['enabled']

    def need(*keys):
        for key in keys:
            if key not in products:
                raise PipelineError(f'{key}: required product missing; producer OFF and no explicit compatible input')
        return tuple(keys)

    def add(entry, *keys):
        name = entry.stages[0].name if isinstance(entry, ArtifactGroup) else entry.name
        requirements[name] = need(*keys)
        entries.append(entry)

    bind('preanalysis', 'preanalysis', None, inputs['preanalysis_dir'], on('preanalysis'),
         settings['preanalysis']['output_dir'], 'common:preanalysis')
    bind('calibration', 'calibration', None, inputs['calibration'], on('calibration'),
         {'root': paths.calibrated_flux, 'qa': paths.calibrated_flux.with_suffix('.qa.json')}, 'common:calibrate_flux')
    for profile in ('uv', 'vis'):
        base = paths.profile_root(profile)
        for kind, stage, generated, producer in (
            ('selected', 'selection', paths.selected_dir(profile), f'{profile}:select'),
            ('mc', 'monte_carlo', paths.mc_dir(profile), f'{profile}:mc_status'),
            ('bdt', 'bdt', paths.bdt_dir(profile) / 'artifacts/stage1', f'{profile}:train'),
            ('reconstruction', 'reconstruction', {'chi2': base / 'reco/reco_eta_pi0_chi2.root', 'bdt': base / 'reco/reco_eta_pi0_bdt.root'}, f'{profile}:reconstruct_bdt'),
            ('extraction', 'extraction', base / 'beam_asymmetry/beam_asymmetry.root', f'{profile}:extract'),
        ):
            bind(f'{kind}.{profile}', kind, profile, inputs[kind][profile], on(stage, profile), generated, producer)

    if on('preanalysis'):
        if inputs['raw_dir'] is None:
            raise PipelineError('preanalysis ON requires inputs.raw_dir')
        command = _argv(python_executable, checkout / 'scripts/run_preanalysis.py', '--raw-dir', inputs['raw_dir'],
                        '--output-dir', products['preanalysis'].value, '--cpus', data['execution']['cpus'])
        if settings['preanalysis']['cuts_dir']:
            command += _argv('--cuts-dir', settings['preanalysis']['cuts_dir'])
        add(Stage('common:preanalysis', command, kind='preanalysis'))
    if on('calibration'):
        need('preanalysis')
        stage = _common_stages(python_executable, paths, mode)[0]
        options = {k: v for k, v in settings['calibration'].items() if k not in ('enabled', 'common_inputs')}
        add(with_options(stage, preanalysis_dir=products['preanalysis'].value, **options), 'preanalysis')
    if on('flux_study'):
        need('calibration')
        cfg, calibration = settings['flux_study'], products['calibration'].value
        module = 'audit_flux' if cfg['mode'] == 'audit' else 'study_missing_flux'
        command = _argv(python_executable, '-m', f'flux_studies.{module}', '--manifest', paths.manifest,
                        '--raw-flux', paths.raw_flux, '--calibrated-flux', calibration['root'], '--calibration-qa', calibration['qa'],
                        '--output-dir', checkout / 'results_test/diagnostics' / paths.output_root.name / 'missing_flux')
        if cfg['metadata']:
            command += _argv('--run-metadata', cfg['metadata'])
        add(Stage(f'common:flux_{cfg["mode"]}', command, kind=f'flux_{cfg["mode"]}'), 'calibration')

    for profile in ('uv', 'vis'):
        if not data['profiles'][profile]['enabled']:
            continue
        cfg = {name: settings[name][profile] for name in ('selection', 'monte_carlo', 'bdt', 'reconstruction', 'extraction', 'plots')}
        grid = EnergyBinning(data['profiles'][profile]['energy_edges_gev'])
        channels = tuple(name for name in cfg['monte_carlo']['channels']
                         if get_channel(name).production_threshold_gev < grid.energy_range_gev[1])
        # Build shared command definitions even for partial plans, then select only ON stages.
        template_channels = channels if 'eta_pi0' in channels else ('eta_pi0',)
        template = _profile_stages(profile, template_channels, replace(mode, mc_events=cfg['monte_carlo']['events_per_channel']),
                                   paths, PreflightResult(root_executable), python_executable,
                                   cfg['extraction']['phi_bins'], grid,
                                   require_mc_support=on('monte_carlo', profile) or on('bdt', profile))
        for entry in template:
            if isinstance(entry, ArtifactGroup):
                owner = {'selected': 'selection', 'mc': 'monte_carlo', 'bdt': 'bdt'}[entry.kind]
                if not on(owner, profile):
                    continue
                entry = replace(entry, force=cfg[owner]['force'])
                if entry.kind == 'selected':
                    need('preanalysis')
                    select = with_options(entry.stages[0], input_dir=products['preanalysis'].value, pattern=cfg['selection']['pattern'])
                    add(replace(entry, stages=(select,)), 'preanalysis')
                elif entry.kind == 'mc':
                    add(entry)
                else:
                    need(f'selected.{profile}', f'mc.{profile}')
                    selected, mc = products[f'selected.{profile}'].value, products[f'mc.{profile}'].value
                    spectrum, features, train = entry.stages
                    spectrum = with_options(spectrum, selected_dir=selected)
                    if not any(name != 'eta_pi0' for name in channels):
                        raise PipelineError(f'bdt.{profile}: at least one background MC channel is required')
                    features = with_options(features, mc_dir=mc)
                    train = with_options(train, hyperparams=cfg['bdt']['hyperparams'] or paths.hyperparams,
                                         val_fraction=cfg['bdt']['validation_fraction'], seed=cfg['bdt']['training_seed'])
                    if cfg['bdt']['feature_diagnostics']:
                        train = with_options(train, feature_diagnostics_dir=entry.destination / 'feature_diagnostics')
                    bound_inputs = (selected, *(mc / get_channel(name).mc_filename for name in channels))
                    add(replace(entry, stages=(spectrum, features, train), inputs=bound_inputs), f'selected.{profile}', f'mc.{profile}')
            elif entry.kind == 'mc_status' and on('monte_carlo', profile):
                add(entry)
            elif entry.kind.startswith('reconstruct_') and on('reconstruction', profile):
                need(f'selected.{profile}', f'bdt.{profile}')
                entry = with_options(entry, input_dir=products[f'selected.{profile}'].value, chi2_cut=cfg['reconstruction']['chi2_cut'],
                                     missing_mass_window=cfg['reconstruction']['missing_mass_window_gev'])
                if entry.kind == 'reconstruct_bdt':
                    entry = with_options(entry, model_dir=products[f'bdt.{profile}'].value)
                add(entry, f'selected.{profile}', f'bdt.{profile}')
            elif entry.kind == 'extract' and on('extraction', profile):
                need(f'reconstruction.{profile}', 'calibration')
                reco, calibration = products[f'reconstruction.{profile}'].value, products['calibration'].value
                options = {key: value for key, value in cfg['extraction'].items()
                           if key not in ('enabled', 'workers', 'candle_enabled', 'candle_mass_half_width_gev')}
                entry = with_options(entry, raw=reco['chi2'], raw_bdt=reco['bdt'], flux_file=calibration['root'],
                                     candle_mass_half_width=cfg['extraction']['candle_mass_half_width_gev'] if cfg['extraction']['candle_enabled'] else None,
                                     **options)
                add(entry, f'reconstruction.{profile}', 'calibration')
        if on('plots', profile):
            need(f'reconstruction.{profile}')
            reco = products[f'reconstruction.{profile}'].value
            command = _argv(python_executable, checkout / 'scripts/plot_campaign.py', '--reconstruction-only', '--profile', profile,
                            '--chi2', reco['chi2'], '--bdt', reco['bdt'], '--output-dir', paths.output_root / 'plots' / profile / 'reconstruction')
            for key in ('mass', 'quality_controls', 'dalitz'):
                command += ('--' + ('' if cfg['plots'][key] else 'no-') + key.replace('_', '-'),)
            # Plot renderer owns its process budget; legacy campaign --workers is not used here.
            add(Stage(f'{profile}:plots', command, kind='reconstruction_plots', profile=profile), f'reconstruction.{profile}')
    if on('comparison'):
        if not all(data['profiles'][p]['enabled'] for p in ('uv', 'vis')):
            raise PipelineError('comparison ON requires both UV and VIS profiles enabled')
        need('extraction.uv', 'extraction.vis')
        command = _argv(python_executable, '-m', 'observable_extraction.combine_profiles',
                        '--uv-root', products['extraction.uv'].value, '--vis-root', products['extraction.vis'].value,
                        '--published-csv', settings['comparison']['published_reference'] or paths.ajaka_reference,
                        '--output-dir', paths.combined_dir)
        add(Stage('common:comparison', command, kind='comparison'), 'extraction.uv', 'extraction.vis')
    entries = configure_resources(tuple(entries), cpus=data['execution']['cpus'], seed=data['execution']['seed'])
    entries = tuple(with_options(entry, workers=settings['extraction'][entry.profile]['workers'])
                    if isinstance(entry, Stage) and entry.kind == 'extract' else entry for entry in entries)
    return CampaignPlan(configuration, mode, paths, entries, products, requirements)
