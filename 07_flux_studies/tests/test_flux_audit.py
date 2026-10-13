import pytest
from flux_studies.tests.helpers import audit_inputs


def test_raw_present_is_not_missing_raw_and_brem_zero_valid(tmp_path):
    from flux_studies.audit_flux import audit_flux
    result = audit_flux(**audit_inputs(tmp_path))
    row = next(r for r in result['rows'] if r['state'] == 'POL1')
    assert 'missing_raw' not in row['problems']
    assert 'missing_calibrated' in row['problems']
    assert row['coverage'] == 'unknown'
    brem = next(r for r in result['rows'] if r['state'] == 'BREM')
    assert brem['raw_integral'] == 0
    assert brem['raw_usable']
    assert not brem['shape_usable']


@pytest.mark.parametrize('kwargs, problem', [({'missing': ('POL2',)}, 'missing_raw'), ({'duplicate': 'POL2'}, 'duplicate_raw'), ({'negative': True}, 'negative_content')])
def test_defects_are_reported_without_aborting(tmp_path, kwargs, problem):
    from flux_studies.audit_flux import audit_flux
    result = audit_flux(**audit_inputs(tmp_path, **kwargs))
    assert len(result['rows']) == 3
    assert any(problem in row['problems'] for row in result['rows'])


def test_stale_qa_cannot_claim_coverage(tmp_path):
    from flux_studies.audit_flux import audit_flux
    from calibration.calibration_qa import write_calibration_qa
    inputs = audit_inputs(tmp_path)
    qa = tmp_path/'qa.json'
    write_calibration_qa(qa, inputs['calibrated_flux'], inputs={'raw_flux':'wrong'}, coverage=[], diagnostics={})
    result = audit_flux(**inputs, calibration_qa=qa)
    assert result['summary']['qa_status'] == 'identity_mismatch'
    assert all(r['coverage']=='unknown' for r in result['rows'])


@pytest.mark.parametrize('kind,problem',[('alias','noncanonical_name'),('nan','nonfinite_content'),('th2','not_1d_histogram'),('bins','wrong_bin_count'),('axis','invalid_strip_axis')])
def test_malformed_root_objects_survive_inventory(tmp_path,kind,problem):
    import ROOT
    from flux_studies.audit_flux import audit_flux
    inputs=audit_inputs(tmp_path,missing=('POL2',))
    output=ROOT.TFile(str(inputs['raw_flux']),'UPDATE')
    if kind=='th2':hist=ROOT.TH2D('run7_POL2','',128,0,128,2,0,2)
    else:
        hist=ROOT.TH1D('run07_POL2' if kind=='alias' else 'run7_POL2','',12 if kind=='bins' else 128,1 if kind=='axis' else 0,128)
        hist.SetBinContent(1,float('nan') if kind=='nan' else 1)
    hist.Write();output.Close()
    result=audit_flux(**inputs)
    assert len(result['rows'])==3
    assert any(problem in row['problems'] for row in result['rows'])
