"""Independent closure of local target edges, including nonuniform acceptance."""
import numpy as np
import pytest
from calibration.target_edges import fit_edges


@pytest.mark.parametrize('length,center,curvature',[(3.,-.5,0.),(6.12,.14,0.),(11.6,.4,.65),(12.,-.3,.65)])
def test_local_edges_recover_short_and_long_cells_without_nominal_constraint(length,center,curvature):
    rng=np.random.default_rng(812)
    truth=rng.uniform(center-length/2,center+length/2,100000)
    efficiency=1-curvature*(2*(truth-center)/length)**2
    mask=rng.random(len(truth))<efficiency
    z=np.r_[truth[mask]+rng.normal(0,.15,mask.sum()),rng.uniform(-15,15,1500)]
    result=fit_edges(z)
    assert result['status']=='approximate'
    assert result['length_cm']==pytest.approx(length,abs=.15)
    assert result['center_cm']==pytest.approx(center,abs=.1)
    assert result['model_scope']=='local_edges'
    model=np.array(result['expected_counts'],float)
    assert np.isnan(model).any()  # No invented flat density in the cell interior.
    assert result['length_stat_error_cm'] is None


def test_no_vertices_or_too_few_does_not_invent_target():
    for z in ([],[0.,.1,-.1]):
        result=fit_edges(z)
        assert result['length_cm'] is None
        assert result['status']=='insufficient_statistics'


def test_nonfinite_input_rejected():
    with pytest.raises(ValueError,match='finite'):
        fit_edges([0.,np.nan])


def test_bootstrap_reports_conditional_length_error():
    rng=np.random.default_rng(93)
    z=rng.uniform(-3.,3.,10000)+rng.normal(0,.15,10000)
    result=fit_edges(z,bootstrap=8,seed=4)
    assert result['bootstrap_successful']>=8
    assert result['length_stat_error_cm']>0
