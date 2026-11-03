"""Versioned Gaussian candle selection provenance; legacy rectangles stay readable."""
import json
import math

from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.core.candle import GaussianCandle


def gaussian_candle_provenance(split, baseline_count, half_width_gev):
    return [
        'candle_enabled=true', 'candle_geometry=gaussian_ellipse',
        'candle_core_logic=mahalanobis_50_percent', 'candle_tail_logic=finite_complement',
        'candle_boundary=inclusive', 'candle_balance_method=none',
        'candle_mass_source=raw_pre_fit',
        f'candle_mass_half_width_gev={half_width_gev}',
        f'candle_baseline_event_count={baseline_count}',
        f'candle_full_core_event_count={split.full_core_count}',
        f'candle_tail_event_count={split.tail_count}',
        f'candle_excluded_nonfinite_event_count={split.excluded_nonfinite_count}',
        'candle_gaussian_model=' + json.dumps(split.gaussian_model.to_dict(), allow_nan=False, sort_keys=True),
    ]


def parse_gaussian_candle(values, contract_type):
    semantics = dict(candle_enabled='true', candle_geometry='gaussian_ellipse',
                     candle_core_logic='mahalanobis_50_percent', candle_tail_logic='finite_complement',
                     candle_boundary='inclusive', candle_balance_method='none', candle_mass_source='raw_pre_fit')
    count_keys = ('candle_baseline_event_count', 'candle_full_core_event_count',
                  'candle_tail_event_count', 'candle_excluded_nonfinite_event_count')
    required = {*semantics, *count_keys, 'candle_mass_half_width_gev', 'candle_gaussian_model'}
    if {key for key in values if key.startswith('candle_')} != required:
        raise ValueError('incomplete or unknown Gaussian candle fields')

    def one(key):
        if len(values[key]) != 1 or not values[key][0]:
            raise ValueError(f'invalid {key}')
        return values[key][0]

    if any(one(key) != value for key, value in semantics.items()):
        raise ValueError('invalid Gaussian candle semantics')
    baseline, core, tails, excluded = (int(one(key)) for key in count_keys)
    if min(baseline, core, tails) <= 0 or excluded < 0 or core + tails + excluded != baseline:
        raise ValueError('invalid Gaussian candle counts')
    width = float(one('candle_mass_half_width_gev'))
    if not math.isfinite(width) or width <= 0:
        raise ValueError('invalid Gaussian fit window')
    model = GaussianCandle.from_dict(json.loads(one('candle_gaussian_model')))
    fit = model.to_dict()['fit']
    if fit is None or fit['input_count'] != baseline or fit['finite_count'] != baseline - excluded:
        raise ValueError('Gaussian fit provenance does not match baseline')
    for bounds, center in zip(model.fit_window_gev, (M_ETA, M_PI0)):
        if any(not math.isclose(value, expected, rel_tol=0, abs_tol=1e-12)
               for value, expected in zip(bounds, (center - width, center + width))):
            raise ValueError('Gaussian fit window does not match declared width')
    return contract_type(
        eta_center_gev=model.eta_center_gev, pi0_center_gev=model.pi0_center_gev,
        mass_half_width_gev=width, geometry='gaussian_ellipse',
        core_logic='mahalanobis_50_percent', tail_logic='finite_complement', boundary='inclusive',
        baseline_event_count=baseline, full_core_event_count=core, tail_event_count=tails,
        balanced_core_event_count=core, excluded_nonfinite_event_count=excluded,
        balance_method='none', balance_seed=0, mass_source='raw_pre_fit', gaussian_model=model)
