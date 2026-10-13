import numpy as np
import pytest


def test_linear_uses_time_and_requires_bracket():
    from flux_studies.methods import baseline_prediction
    values=np.zeros((2,128));values[0,0]=1;values[1,1]=1
    result=baseline_prediction('linear',np.array([10.,30.]),values,15.)
    np.testing.assert_allclose(result['values'][:2],[.75,.25])
    assert result['donor_indices']==[0,1]
    assert baseline_prediction('linear',np.array([10.,30.]),values,40.)['status']=='not_reconstructible'
    assert baseline_prediction('linear',np.array([10.,10.]),values,10.)['status']=='not_reconstructible'


def test_shapes_and_multioutput_fit():
    from flux_studies.methods import normalize_shape,project_shape,fit_ridge
    for value in (np.zeros(128),np.full(128,-1.),np.full(128,np.nan)):
        with pytest.raises(ValueError):normalize_shape(value)
    values=np.ones(128);values[0]=-1
    shape=project_shape(values)
    assert shape[0]==0
    assert shape.sum()==pytest.approx(1)
    X=np.arange(12.).reshape(6,2);y=np.tile(X[:,0,None],(1,128))
    model=fit_ridge(X,y,alpha=.001)
    assert model.predict(X).shape==(6,128)
    np.testing.assert_allclose(model.named_steps['standardscaler'].mean_,[5,6])
