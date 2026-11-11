"""Figure-derived rho on measured support, without extrapolation."""
from __future__ import annotations
from bisect import bisect_right
from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class HelicityRatio:
    energy_lab_gev: tuple[float, ...]
    rho: tuple[float, ...]

    def __post_init__(self):
        if len(self.energy_lab_gev) < 2 or len(self.energy_lab_gev) != len(self.rho):
            raise ValueError('ratio requires paired nodes')
        if not all(math.isfinite(x) for x in (*self.energy_lab_gev,*self.rho)):
            raise ValueError('nonfinite helicity input')
        if any(b <= a for a,b in zip(self.energy_lab_gev,self.energy_lab_gev[1:])):
            raise ValueError('energies must strictly increase')
        if self.energy_lab_gev[0] < 1. or self.energy_lab_gev[-1] > 1.4:
            raise ValueError('nodes outside authorized energy domain')

    def evaluate(self, egamma_gev: float) -> float:
        x = self.energy_lab_gev
        if not math.isfinite(egamma_gev) or not x[0] <= egamma_gev <= x[-1]:
            raise ValueError(f'energy outside measured support [{x[0]}, {x[-1]}] GeV')
        if egamma_gev == x[-1]: return self.rho[-1]
        i = bisect_right(x,egamma_gev)-1
        t = (egamma_gev-x[i])/(x[i+1]-x[i])
        return self.rho[i] + t*(self.rho[i+1]-self.rho[i])


def load_ratio(path: Path) -> HelicityRatio:
    data = json.loads(Path(path).read_text())
    try:
        if (data['schema_version'],data['baseline'],data['solution']) != (1,'Fix2010','I'):
            raise ValueError('unsupported ratio baseline/solution')
        if data['units'] != {'energy_lab_gev':'GeV','rho':'dimensionless'}:
            raise ValueError('unsupported ratio units')
        if data['quantity'] != 'A_3/2 / A_1/2' or data['interpolation'] != 'piecewise_linear_no_extrapolation':
            raise ValueError('wrong helicity quantity or interpolation')
        if data['source']['archive_sha256'] != '703501be0948d5a68ce189fd69968c26819aa3e13c9ea80f69fcd2b438674f11' or data['source']['member_sha256'] != '10180ad940497afd6dc4886b48ad4865e17faa6ce4582efb3b57b98616eebf1f':
            raise ValueError('helicity source hash mismatch')
        ratio = HelicityRatio(tuple(data['energy_lab_gev']),tuple(data['rho']))
        if data['support_lab_gev'] != [ratio.energy_lab_gev[0],ratio.energy_lab_gev[-1]]:
            raise ValueError('support does not match nodes')
        error = data['reading_error']['vertical_envelope_rho']
        if not math.isfinite(error) or error <= 0:
            raise ValueError('reading uncertainty required')
        return ratio
    except (KeyError,TypeError) as exc:
        raise ValueError('incomplete helicity input') from exc
