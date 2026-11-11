"""Reject incomplete dynamics and scientifically incompatible catalogs."""
import json
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[2]/'data/theory/fix2010/parameters_solution_i.json'


def test_inventory_preserves_signs_units_spin_and_fitted_mass():
    from graal_theory.parameters import inspect_parameters, load_parameters, IncompleteModelError
    inventory = inspect_parameters(SOURCE)
    assert inventory.resonances[1].production_product_gev_mhalf == -.0001
    assert inventory.resonances[2].mass_gev == 1.832
    assert inventory.resonances[2].rho_at_mass is None
    assert inventory.resonances[2].helicity_three_half == 'forbidden'
    assert inventory.resonances[5].mass_gev == 1.870
    with pytest.raises(IncompleteModelError, match='G0'):
        load_parameters(SOURCE)
    with pytest.raises((AttributeError,TypeError)):
        inventory.resonances[0].mass_gev = 1.7


@pytest.mark.parametrize('fault', ['missing','solution','units','mev','nominal','nan','spin','forged_complete','gap_removed','conversion'])
def test_invalid_parameters(tmp_path, fault):
    from graal_theory.parameters import inspect_parameters
    d=json.loads(SOURCE.read_text())
    r=d['resonances'][0]
    if fault=='missing': del r['width_at_mass_gev']
    if fault=='solution': d['resonances'][3]['solution']='II'
    if fault=='units': del d['units']['energy']
    if fault=='mev': r['width_at_mass_gev']=375
    if fault=='nominal': r['mass_gev']=1.700; r['original']['mass']['value']=1700
    if fault=='nan': r['production_product_gev_mhalf']=float('nan')
    if fault=='spin': d['resonances'][2]['rho_at_mass']={'value':0.,'error':0.}
    if fault=='forged_complete': d['status']='complete'
    if fault=='gap_removed': d['gaps']=[]
    if fault=='conversion': r['production_product_gev_mhalf']=10.6
    path=tmp_path/'input.json'; path.write_text(json.dumps(d))
    with pytest.raises(ValueError): inspect_parameters(path)


@pytest.mark.parametrize('value', ['not a number', [], None, True, False])
def test_allowed_helicity_requires_numeric_ratio(tmp_path, value):
    from graal_theory.parameters import inspect_parameters
    data=json.loads(SOURCE.read_text())
    data['resonances'][0]['rho_at_mass']['value']=value
    path=tmp_path/'bad-rho.json'; path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='numeric'):
        inspect_parameters(path)


def test_negative_helicity_ratio_preserved():
    from graal_theory.parameters import inspect_parameters
    assert inspect_parameters(SOURCE).resonances[3].rho_at_mass == -.70
