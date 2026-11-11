"""Catch wrong ratio, silent extrapolation and corrupted curated input."""
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
RATIO = ROOT / 'data/theory/fix2010/helicity_ratio_fig6_solution_i.json'


def test_linear_ratio_and_support():
    from graal_theory.helicity import load_ratio
    ratio = load_ratio(RATIO)
    assert ratio.evaluate(1.0) == pytest.approx(182 * 3 / 554)
    assert ratio.evaluate(1.2) == pytest.approx(192 * 3 / 554, abs=.002)
    assert ratio.evaluate(ratio.energy_lab_gev[-1]) == pytest.approx(244 * 3 / 554)
    # Independent physical-coordinate interpolation at midpoint of first segment.
    assert ratio.evaluate((ratio.energy_lab_gev[0] + ratio.energy_lab_gev[1])/2) == ratio.rho[0]
    for energy in [.99, 1.4, 1.41, float('nan'), float('inf')]:
        with pytest.raises(ValueError):
            ratio.evaluate(energy)


@pytest.mark.parametrize('fault', ['duplicate', 'unordered', 'nan', 'solution', 'hash', 'units'])
def test_reject_corrupt_ratio(tmp_path, fault):
    from graal_theory.helicity import load_ratio
    data = json.loads(RATIO.read_text())
    if fault == 'duplicate': data['energy_lab_gev'][1] = data['energy_lab_gev'][0]
    if fault == 'unordered': data['energy_lab_gev'][1] = .9
    if fault == 'nan': data['rho'][1] = float('nan')
    if fault == 'solution': data['solution'] = 'II'
    if fault == 'hash': data['source']['member_sha256'] = '0' * 64
    if fault == 'units': data['units']['energy_lab_gev'] = 'MeV'
    p = tmp_path / 'bad.json'
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError): load_ratio(p)
