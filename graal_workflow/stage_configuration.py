"""Strict, side-effect-free normalization of the stage-oriented YAML contract."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Sequence

import yaml

from graal_common.parallel import available_cpus
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import get_channel
from graal_common.physics.energy_binning import EnergyBinning, load_energy_config
from observable_extraction.core.binning import PHI_BIN_CHOICES
from .configuration import _ConfigLoader, read_config
from .models import PROFILE_PATTERNS, UV_CHANNELS, VIS_CHANNELS


@dataclass(frozen=True)
class StageConfiguration:
    data: dict
    source: Path | None
    source_text: str
    overrides: list[str]


PROFILE_STAGES = ('selection', 'monte_carlo', 'bdt', 'reconstruction', 'extraction', 'plots')
COMMON_STAGES = ('preanalysis', 'calibration', 'flux_study', 'comparison')
# None defaults represent optional, omitted paths; explicit YAML null is rejected.
STAGE_DEFAULTS = {
    'preanalysis': {'output_dir': None, 'cuts_dir': None},
    'selection': {'force': False, 'pattern': '', 'require_current_preanalysis': False},
    'monte_carlo': {'force': False, 'events_per_channel': 1_000_000, 'channels': []},
    'bdt': {'force': False, 'hyperparams': None, 'validation_fraction': 0.2,
            'training_seed': 42, 'feature_diagnostics': False},
    'reconstruction': {'chi2_cut': 10.0, 'missing_mass_window_gev': 0.06},
    'calibration': {'common_inputs': None, 'min_events_per_strip': 1, 'max_mad_gev': 0.005,
                    'monotonic_tolerance_gev': 0.002, 'samples_per_run_strip': 256},
    'flux_study': {'mode': 'audit', 'metadata': None},
    'extraction': {'estimator': 'both', 'phi_bins': 12, 'best_binning': False, 'mass_bins': 10,
                   'by_period': True, 'workers': 1, 'bootstrap_replicas': 0,
                   'bootstrap_seed': 1208, 'candle_enabled': True,
                   'candle_mass_half_width_gev': 0.05, 'candle_balance_seed': 20261024},
    'plots': {'mass': True, 'quality_controls': True, 'dalitz': False},
    'comparison': {'published_reference': None},
}
INPUT_DEFAULTS = {
    'raw_dir': None, 'preanalysis_dir': None,
    **{key: {'uv': None, 'vis': None} for key in ('selected', 'mc', 'bdt', 'extraction')},
    'calibration': {'root': None, 'qa': None},
    'reconstruction': {p: {'chi2': None, 'bdt': None} for p in ('uv', 'vis')},
}


def _error(key: str, message: str):
    raise ValueError(f'{key}: {message}')


def _mapping(value: Any, key: str) -> dict:
    if not isinstance(value, dict):
        _error(key, 'must be a mapping')
    return value


def _field(value: Any, default: Any, key: str, base: Path):
    leaf = key.rsplit('.', 1)[-1]
    if default is None or isinstance(default, Path):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            _error(key, 'must be a nonempty path; omit optional fields instead of null')
        path = Path(value).expanduser()
        return (base / path).resolve() if not path.is_absolute() else path.resolve()
    expected = type(default)
    if expected is float:
        if type(value) not in (int, float) or not math.isfinite(value):
            _error(key, 'must be a finite number')
        value = float(value)
    elif type(value) is not expected:
        _error(key, f'must be {expected.__name__}')
    if expected is int:
        minimum = 0 if leaf in ('training_seed', 'bootstrap_seed', 'bootstrap_replicas', 'candle_balance_seed') else 1
        if value < minimum:
            _error(key, f'must be at least {minimum}')
        if leaf in ('seed', 'training_seed', 'bootstrap_seed', 'candle_balance_seed') and value >= 2**32:
            _error(key, 'must be less than 2**32')
    if expected is float:
        if leaf == 'validation_fraction':
            if not 0 < value < 1:
                _error(key, 'must lie strictly between 0 and 1')
        elif leaf == 'monotonic_tolerance_gev':
            if value < 0:
                _error(key, 'must be nonnegative')
        elif value <= 0:
            _error(key, 'must be positive')
    if expected is str and not value.strip():
        _error(key, 'must be a nonempty string')
    choices = {
        'color': ('auto', 'always', 'never'), 'estimator': ('ratio', 'likelihood', 'both'),
        'phi_bins': PHI_BIN_CHOICES,
    }
    if leaf == 'mode':
        choices[leaf] = ('production', 'test_data') if key.startswith('campaign.') else ('audit', 'study')
    if leaf in choices and value not in choices[leaf]:
        _error(key, f'must be one of {list(choices[leaf])}')
    if leaf == 'channels':
        if not value or any(type(item) is not str for item in value) or len(set(value)) != len(value):
            _error(key, 'must be a nonempty list of distinct channel names')
        for channel in value:
            try:
                get_channel(channel)
            except (ValueError, KeyError) as exc:
                _error(key, str(exc))
    return deepcopy(value)


def _merge(values: dict, defaults: dict, key: str, base: Path) -> dict:
    _mapping(values, key)
    result = deepcopy(defaults)
    for name, value in values.items():
        location = f'{key}.{name}' if key else name
        if name not in defaults:
            _error(location, 'unknown configuration key')
        if isinstance(defaults[name], dict):
            result[name] = _merge(value, defaults[name], location, base)
        else:
            result[name] = _field(value, defaults[name], location, base)
    return result


def _normalize(values: dict, base: Path) -> dict:
    allowed = {'schema_version', 'campaign', 'execution', 'inputs', 'profiles', 'stages'}
    for key in values:
        if key not in allowed:
            _error(str(key), 'unknown configuration key; do not mix legacy and structured YAML')
    if type(values.get('schema_version')) is not int or values['schema_version'] != 1:
        _error('schema_version', 'must be integer 1')
    campaign = _merge(values.get('campaign', {}), {'mode': 'production', 'repo_root': None,
                      'output_dir': None, 'compare_to': None}, 'campaign', base)
    execution = _merge(values.get('execution', {}), {'cpus': available_cpus(), 'seed': 42,
                       'color': 'auto', 'check_only': False}, 'execution', base)
    inputs = _merge(values.get('inputs', {}), INPUT_DEFAULTS, 'inputs', base)
    profiles = _mapping(values.get('profiles', {}), 'profiles')
    for name in profiles:
        if name not in ('uv', 'vis'):
            _error(f'profiles.{name}', 'unknown profile')
    resolved_profiles = {}
    for name in ('uv', 'vis'):
        settings = _mapping(profiles.get(name, {}), f'profiles.{name}')
        if 'enabled' not in settings:
            _error(f'profiles.{name}.enabled', 'explicit enabled switch is required')
        resolved = _merge(settings, {'enabled': False, 'energy_edges_gev': list(get_beam_profile(name).energy_edges_gev)}, f'profiles.{name}', base)
        try:
            grid = EnergyBinning(resolved['energy_edges_gev']).validate_profile(get_beam_profile(name))
        except ValueError as exc:
            _error(f'profiles.{name}.energy_edges_gev', str(exc))
        resolved['energy_edges_gev'] = list(grid.edges_gev)
        resolved_profiles[name] = resolved
    stages = _mapping(values.get('stages', {}), 'stages')
    for name in stages:
        if name not in STAGE_DEFAULTS:
            _error(f'stages.{name}', 'unknown stage')
    resolved_stages = {}
    for name, defaults in STAGE_DEFAULTS.items():
        key = f'stages.{name}'
        if name not in stages:
            _error(key, 'stage section with explicit enabled switch is required')
        settings = _mapping(stages[name], key)
        defaults = {'enabled': False, **defaults}
        if name in COMMON_STAGES:
            if 'enabled' not in settings:
                _error(f'{key}.enabled', 'explicit enabled switch is required')
            resolved_stages[name] = _merge(settings, defaults, key, base)
            continue
        for part in settings:
            if part not in ('common', 'uv', 'vis'):
                _error(f'{key}.{part}', 'expected common, uv or vis')
        common = _mapping(settings.get('common', {}), f'{key}.common')
        # Validate common even if each profile overrides its value.
        _merge(common, defaults, f'{key}.common', base)
        resolved_stages[name] = {}
        for profile in ('uv', 'vis'):
            specific = _mapping(settings.get(profile, {}), f'{key}.{profile}')
            profile_defaults = deepcopy(defaults)
            if name == 'selection':
                profile_defaults['pattern'] = PROFILE_PATTERNS[profile]
            if name == 'monte_carlo':
                profile_defaults['events_per_channel'] = 100_000 if campaign['mode'] == 'test_data' else 1_000_000
                energy_max = resolved_profiles[profile]['energy_edges_gev'][-1]
                channels = UV_CHANNELS if profile == 'uv' else VIS_CHANNELS
                profile_defaults['channels'] = [c for c in channels if get_channel(c).production_threshold_gev < energy_max]
            _merge(specific, defaults, f'{key}.{profile}', base)
            if resolved_profiles[profile]['enabled'] and 'enabled' not in common and 'enabled' not in specific:
                _error(f'{key}.{profile}.enabled', 'explicit enabled switch is required directly or in common')
            resolved = _merge({**common, **specific}, profile_defaults, f'{key}.{profile}', base)
            if name == 'monte_carlo':
                supported = UV_CHANNELS if profile == 'uv' else VIS_CHANNELS
                for channel in resolved['channels']:
                    if channel not in supported or get_channel(channel).production_threshold_gev >= resolved_profiles[profile]['energy_edges_gev'][-1]:
                        _error(f'{key}.{profile}.channels', f'{channel} has no support in the requested profile/energy range')
            resolved_stages[name][profile] = resolved
    return {'schema_version': 1, 'campaign': campaign, 'execution': execution, 'inputs': inputs,
            'profiles': resolved_profiles, 'stages': resolved_stages}


def _assign(data: dict, dotted: str, value: Any, *, base: Path):
    parts = dotted.split('.')
    if parts[0] == 'schema_version':
        _error(dotted, 'schema_version cannot be overridden')
    if len(parts) == 4 and parts[0] == 'stages' and parts[1] in PROFILE_STAGES and parts[2] == 'common':
        for profile in ('uv', 'vis'):
            _assign(data, '.'.join([*parts[:2], profile, parts[3]]), value, base=base)
        return
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            _error(dotted, 'unknown leaf configuration key')
        node = node[part]
    if parts[-1] not in node or isinstance(node[parts[-1]], dict):
        _error(dotted, 'only known leaf configuration keys can be overridden')
    default = node[parts[-1]]
    node[parts[-1]] = _field(value, default, dotted, base)


CLI_KEYS = {
    'mode': 'campaign.mode', 'repo_root': 'campaign.repo_root', 'output_dir': 'campaign.output_dir',
    'cpus': 'execution.cpus', 'seed': 'execution.seed', 'color': 'execution.color',
    'check': 'execution.check_only', 'preanalysis_dir': 'inputs.preanalysis_dir',
    'require_current_preanalysis': 'stages.selection.common.require_current_preanalysis',
    'force_selected': 'stages.selection.common.force', 'force_mc': 'stages.monte_carlo.common.force',
    'force_bdt': 'stages.bdt.common.force', 'phi_bins': 'stages.extraction.common.phi_bins',
    'best_binning': 'stages.extraction.common.best_binning', 'extraction_workers': 'stages.extraction.common.workers',
    'flux_study_metadata': 'stages.flux_study.metadata',
}


def normalize_stage_configuration(values: dict, *, source: Path | None = None,
                                  source_text: str = '', cli_overrides: dict | None = None,
                                  overrides: Sequence[str] = ()) -> StageConfiguration:
    """Validate YAML, resolve common/profile settings, then explicit CLI overrides."""
    source = source.expanduser().resolve() if source is not None else None
    data = _normalize(deepcopy(values), source.parent if source else Path.cwd())
    recorded = []
    for name, value in (cli_overrides or {}).items():
        if name in CLI_KEYS:
            _assign(data, CLI_KEYS[name], value, base=Path.cwd())
        elif name == 'flux_study':
            data['stages']['flux_study']['enabled'] = value != 'off'
            if value != 'off':
                _assign(data, 'stages.flux_study.mode', value, base=Path.cwd())
        elif name == 'energy_config':
            for profile, grid in load_energy_config(value).items():
                data['profiles'][profile]['energy_edges_gev'] = list(grid.edges_gev)
        else:
            _error(name, 'unsupported structured CLI override')
        recorded.append(f'--{name.replace("_", "-")}={value}')
    seen = set()
    for override in overrides:
        key, separator, raw = override.partition('=')
        if not separator or not key or key.strip() != key:
            _error('--set', f'expected dotted.leaf=value, got {override!r}')
        if key in seen:
            _error(key, 'duplicate --set override')
        seen.add(key)
        try:
            value = yaml.load(raw, Loader=_ConfigLoader)
        except yaml.YAMLError as exc:
            _error(key, f'invalid YAML override value: {exc}')
        _assign(data, key, value, base=Path.cwd())
        recorded.append(override)
    # Resolve defaults affected by mode/energy overrides without changing explicit options.
    for profile in ('uv', 'vis'):
        mc_source = values['stages']['monte_carlo']
        mc = data['stages']['monte_carlo'][profile]
        explicit = {**mc_source.get('common', {}), **mc_source.get(profile, {})}
        for field in ('events_per_channel', 'channels'):
            if field in explicit or any(k in seen for k in (f'stages.monte_carlo.common.{field}', f'stages.monte_carlo.{profile}.{field}')):
                continue
            if field == 'events_per_channel':
                mc[field] = 100_000 if data['campaign']['mode'] == 'test_data' else 1_000_000
            else:
                candidates = UV_CHANNELS if profile == 'uv' else VIS_CHANNELS
                mc[field] = [c for c in candidates if get_channel(c).production_threshold_gev < data['profiles'][profile]['energy_edges_gev'][-1]]
    _validate_effective(data)
    return StageConfiguration(data, source, source_text, recorded)


def _validate_effective(data: dict):
    for profile in ('uv', 'vis'):
        try:
            EnergyBinning(data['profiles'][profile]['energy_edges_gev']).validate_profile(get_beam_profile(profile))
        except ValueError as exc:
            _error(f'profiles.{profile}.energy_edges_gev', str(exc))
        for name in PROFILE_STAGES:
            options = data['stages'][name][profile]
            key = f'stages.{name}.{profile}'
            if options.get('force') and (not options['enabled'] or not data['profiles'][profile]['enabled']):
                _error(f'{key}.force', 'force requires an enabled stage and profile')
            if name == 'extraction' and options['workers'] > data['execution']['cpus']:
                _error(f'{key}.workers', 'must not exceed execution.cpus')
            if name == 'monte_carlo':
                if (data['profiles'][profile]['enabled']
                        and (options['enabled'] or data['stages']['bdt'][profile]['enabled'])
                        and 'eta_pi0' not in options['channels']):
                    _error(f'{key}.channels', 'eta_pi0 signal channel is required for MC or BDT')
                supported = UV_CHANNELS if profile == 'uv' else VIS_CHANNELS
                for channel in options['channels']:
                    if channel not in supported or get_channel(channel).production_threshold_gev >= data['profiles'][profile]['energy_edges_gev'][-1]:
                        _error(f'{key}.channels', f'{channel} has no support in the requested profile/energy range')
    if data['stages']['comparison']['enabled'] and not all(p['enabled'] for p in data['profiles'].values()):
        _error('stages.comparison.enabled', 'comparison requires both profiles enabled')
    if data['stages']['comparison']['enabled']:
        uv, vis = (data['stages']['extraction'][profile] for profile in ('uv', 'vis'))
        fields = ['best_binning', 'candle_enabled']
        if not uv['best_binning'] and not vis['best_binning']:
            fields.append('phi_bins')
        if uv['candle_enabled'] and vis['candle_enabled']:
            fields.append('candle_mass_half_width_gev')
        for field in fields:
            equal = (math.isclose(uv[field], vis[field], rel_tol=0.0, abs_tol=1e-12)
                     if field == 'candle_mass_half_width_gev' else uv[field] == vis[field])
            if not equal:
                _error(f'stages.extraction.uv.{field}',
                       f'comparison requires matching UV/VIS {field}: uv={uv[field]!r}, vis={vis[field]!r}')


def load_stage_configuration(path: Path, *, cli_overrides: dict | None = None,
                             overrides: Sequence[str] = ()) -> StageConfiguration:
    values, source_text = read_config(path)
    return normalize_stage_configuration(values, source=path, source_text=source_text,
                                         cli_overrides=cli_overrides, overrides=overrides)
