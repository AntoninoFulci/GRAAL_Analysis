"""Resumable angular stages and explicit diagnostic status."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from tests.test_angular_fit_checks import moment


def workflow():
    path=Path(__file__).resolve().parents[1]/'scripts/figure4_angular_fit.py'
    assert path.exists(), 'angular workflow missing'
    spec=importlib.util.spec_from_file_location('angular_workflow',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_resumable_stages_survive_interruption_and_fingerprint_change(tmp_path):
    module=workflow()
    calls=[]
    fail=[True]
    def calculate(name):
        calls.append(name)
        if name=='mass' and fail[0]:
            raise RuntimeError('interrupted')
        return moment()
    with pytest.raises(RuntimeError,match='interrupted'):
        module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)
    assert calls==['base','angular','mass']
    fail[0]=False; calls.clear()
    item=module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)
    assert calls==['mass','energy','inner']
    assert item.status=='diagnostic_converged'
    assert item.predict([1.,0.,0.]).sigma==pytest.approx(.2)
    calls.clear()
    module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)
    assert calls==[]
    with pytest.raises(ValueError,match='fingerprint'):
        module.calculate_bin(tmp_path,(0,'p_eta',0),'b'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)


def test_failed_axis_is_recorded_and_cannot_enter_fit(tmp_path):
    from dataclasses import replace
    module=workflow()
    def calculate(name):
        return replace(moment(),status='masked_nonconverged',reason='inner failure') if name=='inner' else moment()
    item=module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)
    assert item.status=='masked_nonconverged'
    assert 'inner' in str(item.reason)
    with pytest.raises(ValueError,match='uncertified'):
        item.predict([1.,0.,0.])


def test_campaign_refuses_execution_from_different_source_tree(tmp_path,monkeypatch):
    import json
    module=workflow()
    original=tmp_path/'original.py'; original.write_text('old snapshot')
    manifest={'policy':module.POLICY,'settings':{},'fingerprint':'a'*64,
              'inputs':{'workflow':str(original),**{name:str(tmp_path/name) for name in
                         ('data_root','reco_root','flux_root','run_manifest')}}}
    (tmp_path/'campaign.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(module,'fingerprint_inputs',lambda *args:'a'*64)
    with pytest.raises(ValueError,match='executing source'):
        module.load_campaign(tmp_path)


def test_real_numeric_exception_saved_as_mask_not_retry_loop(tmp_path):
    module=workflow()
    calls=[]
    def calculate(name):
        calls.append(name)
        if name=='inner':
            raise FloatingPointError('nonfinite loop integral')
        return moment()
    item=module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)
    assert item.status=='masked_nonconverged'
    assert 'nonfinite loop integral' in str(item.reason)
    calls.clear()
    again=module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,calculate,failure_template=moment(),validate_inputs=lambda:None)
    assert again.status=='masked_nonconverged' and calls==[]


def test_changed_inputs_refuse_stage_publication(tmp_path):
    module=workflow()
    def changed():
        raise ValueError('fingerprint changed during calculation')
    with pytest.raises(ValueError,match='fingerprint changed'):
        module.calculate_bin(tmp_path,(0,'p_eta',0),'a'*64,.05,lambda name:moment(),
                             failure_template=moment(),validate_inputs=changed)
    assert not list(tmp_path.rglob('*.npz'))
