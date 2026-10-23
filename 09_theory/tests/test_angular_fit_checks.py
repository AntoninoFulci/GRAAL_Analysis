"""Deterministic diagnostics stay distinct from Sobol certificates."""
from dataclasses import replace

import numpy as np
import pytest

from graal_theory.figure4_basis import BasisBinMoment
from graal_theory.figure4_fit_output import BasisCheckpoint


def moment():
    d=np.eye(3,dtype=complex)
    return BasisBinMoment('p_eta',(1.1,1.2),(1.52,1.56),'uniform',d*.2,d,
        None,None,None,None,None,d*.1,np.array([1.15]),'calculated',
        model_fingerprint='fixed',anchor_g1=-.2,anchor_g2=.3,proton_mass_gev=.938,
        mass_numerator=d*1.54,vertical_normalization=d*.6,horizontal_normalization=d*.4)


def check(base,checks=None):
    from graal_theory.figure4_basis import AngularBinCheck
    return AngularBinCheck(base,'diagnostic_converged',(),
        {name:base for name in ('angular','mass','energy','inner')} if checks is None else checks,.01)


def test_angular_checks_gate_every_trial_and_refuse_missing_axis():
    base=moment()
    assert check(base).predict([1.,0.,0.]).sigma == pytest.approx(.2)
    checks={name:base for name in ('angular','mass','energy','inner')}
    changed=base.numerator.copy(); changed[1,1]+=.005
    checks['mass']=replace(base,numerator=changed)
    diagnostic=check(base,checks)
    diagnostic.predict([1.,0.,0.])
    # Cancellation magnifies otherwise small matrix errors at a trial point.
    tiny=base.denominator.copy(); tiny[1,1]=1e-5
    base=replace(base,denominator=tiny)
    checks={name:base for name in checks}
    checks['mass']=replace(base,numerator=changed)
    diagnostic=check(base,checks)
    with pytest.raises(ValueError,match='refinement'):
        diagnostic.predict([1.,10.,0.])
    with pytest.raises(ValueError,match='checks'):
        check(base,{}).predict([1.,0.,0.])


def test_angular_checkpoint_roundtrip_preserves_policy_and_complex_checks(tmp_path):
    base=moment(); item=check(base)
    checkpoint=BasisCheckpoint.open(tmp_path/'basis',target='native',
        keys=((0,'p_eta',0),),fingerprint='a'*64,resume=False)
    checkpoint.write((0,'p_eta',0),item); checkpoint.finish()
    restored=checkpoint.read((0,'p_eta',0))
    assert type(restored) is type(item)
    assert restored.status == 'diagnostic_converged'
    assert restored.predict([1.,.1,-.2]).sigma == pytest.approx(.2)
    with pytest.raises(ValueError,match='uncertified|diagnostic'):
        replace(restored,status='preliminary_uncertified').predict([1.,0.,0.])


def test_large_matrix_drift_rejected_even_when_source_ratio_unchanged():
    base=moment()
    checks={name:base for name in ('angular','mass','energy','inner')}
    changed=base.denominator.copy(); changed[1,1]*=1.02
    checks['inner']=replace(base,denominator=changed)
    with pytest.raises(ValueError,match='matrix'):
        check(base,checks).predict([1.,0.,0.])
