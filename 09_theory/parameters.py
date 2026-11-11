"""Validated immutable inventory; incomplete physics cannot become model input.

The curated schema is an inventory, not a runnable ModelParameters contract.
A complete contract requires a new reviewed schema after gate G0 is closed.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import NoReturn


class IncompleteModelError(ValueError):
    """A source-verified ingredient required by gate G0 is unavailable."""


@dataclass(frozen=True)
class ResonanceInput:
    name: str
    spin_twice: int
    mass_gev: float
    width_at_mass_gev: float
    production_product_gev_mhalf: float
    helicity_three_half: str
    rho_at_mass: float | None
    decay_ratio_at_mass: float


@dataclass(frozen=True)
class ParameterInventory:
    version: str
    domain_lab_gev: tuple[float, float]
    resonances: tuple[ResonanceInput, ...]
    gaps: tuple[tuple[str, str, str], ...]


# Historical fitted masses are identity constraints for this fixed baseline,
# not configurable masses or replacements taken from a modern PDG edition.
_FITTED = {'D33(1700)':(1.701,3), 'P33(1600)':(1.657,3),
           'P31(1750)':(1.832,1), 'F35(1905)':(1.873,5),
           'P33(1920)':(1.894,3), 'D33(1940)':(1.870,3)}
_REQUIRED_GAPS = {'total_widths','isobar_widths','born','vertex_normalization',
                  'angular_translation','helicity_endpoint'}


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite parameter')
    if isinstance(value, dict):
        for item in value.values(): _finite_tree(item)
    elif isinstance(value, list):
        for item in value: _finite_tree(item)


def inspect_parameters(path: Path) -> ParameterInventory:
    """Read verified numerical inventory without asserting dynamic completeness."""
    d = json.loads(Path(path).read_text())
    _finite_tree(d)
    try:
        if (d['schema_version'],d['baseline'],d['solution'],d['status']) != (1,'Fix2010','I','incomplete'):
            raise ValueError('expected incomplete Fix2010 solution-I inventory schema 1')
        if d['units'] != {'energy':'GeV','angle':'rad','production_product':'GeV^-1/2','cross_section':'microbarn'}:
            raise ValueError('missing or incompatible units')
        if d['domain_lab_gev'] != [1.,1.4]: raise ValueError('wrong laboratory domain')
        if [r['name'] for r in d['resonances']] != list(_FITTED):
            raise ValueError('six solution-I resonances required, in source order')
        records=[]
        for r in d['resonances']:
            mass,spin = _FITTED[r['name']]
            if r['solution'] != 'I' or r['mass_gev'] != mass or r['spin_twice'] != spin:
                raise ValueError('wrong solution, fitted mass or spin')
            if not 0 < r['width_at_mass_gev'] < 1:
                raise ValueError('width must be positive in GeV')
            for key, converted in [('mass','mass_gev'),('width','width_at_mass_gev'),('production_product','production_product_gev_mhalf')]:
                original=r['original'][key]
                unit='10^-3 GeV^-1/2' if key=='production_product' else 'MeV'
                if original['unit'] != unit or not math.isclose(r[converted], original['value']/1000,rel_tol=1e-13,abs_tol=0):
                    raise ValueError('original units and converted values disagree')
            for field in ['mass_error_gev','production_product_error_gev_mhalf']:
                if r[field] < 0: raise ValueError('negative marginal error')
            forbidden = spin == 1
            if r['helicity_three_half'] != ('forbidden' if forbidden else 'allowed'):
                raise ValueError('helicity spin selection violated')
            ratio=r['rho_at_mass']
            if forbidden and ratio is not None: raise ValueError('J=1/2 forbids helicity 3/2')
            if not forbidden and (ratio is None or ratio['error'] < 0):
                raise ValueError('helicity ratio and marginal error required')
            if not forbidden and (type(ratio['value']) not in (int, float)
                                  or not math.isfinite(ratio['value'])):
                raise ValueError('allowed helicity ratio requires a finite numeric value')
            decay=r['decay_ratio_at_mass']
            if decay['value'] < 0 or decay['error'] < 0: raise ValueError('negative branching ratio/error')
            if not r['source']: raise ValueError('source required')
            records.append(ResonanceInput(r['name'],spin,mass,r['width_at_mass_gev'],r['production_product_gev_mhalf'],r['helicity_three_half'],None if forbidden else ratio['value'],decay['value']))
        gaps=tuple((g['id'],g['state'],g['consequence']) for g in d['gaps'])
        if {g[0] for g in gaps} != _REQUIRED_GAPS or len(gaps) != len(_REQUIRED_GAPS):
            raise ValueError('known G0 gaps cannot be removed from inventory schema 1')
        if any(state not in ('missing','ambiguous') or not consequence for _,state,consequence in gaps):
            raise ValueError('gap state and consequence required')
        return ParameterInventory(d['model_version'],tuple(d['domain_lab_gev']),tuple(records),gaps)
    except (KeyError,TypeError) as exc:
        raise ValueError('incomplete parameter inventory') from exc


def load_parameters(path: Path) -> NoReturn:
    """Fail closed: no executable ModelParameters exists until G0 is resolved."""
    inventory=inspect_parameters(path)
    raise IncompleteModelError('G0 incomplete: '+', '.join(g[0] for g in inventory.gaps))
