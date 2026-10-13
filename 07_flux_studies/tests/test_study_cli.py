import json
from flux_studies.tests.helpers import audit_inputs, study_audit


def test_no_metadata_publishes_protocol_without_synthetic_root(tmp_path):
    from flux_studies.study_missing_flux import main
    inputs=audit_inputs(tmp_path)
    output=tmp_path/'out'
    argv=[item for name,path in inputs.items() for item in ('--'+name.replace('_','-'),str(path))]+['--output-dir',str(output)]
    assert main(argv)==0
    data=json.loads((output/'study.json').read_text())
    assert data['status']=='not_executable'
    assert data['reasons']
    assert not (output/'synthetic_flux.root').exists()
    assert json.loads((output/'input_integrity.json').read_text())['unchanged']


def test_holdout_artifact_roundtrip_and_shape_only(tmp_path):
    import ROOT
    from flux_studies.study_missing_flux import run_study
    from flux_studies.reporting import write_study
    audit=study_audit(12)
    result=run_study(audit,mode='offline',n_splits=3,seed=42,n_replicas=3,mask_patterns=(('POL1',),))
    assert result['status']=='exploratory'
    assert all(p['domain']=='shape' for p in result['evaluation']['predictions'])
    write_study(tmp_path,audit,result)
    source=ROOT.TFile.Open(str(tmp_path/'study.root'),'READ')
    assert source.Get('metadata/provenance')
    assert source.Get('holdout/p000000/estimate').GetNbinsX()==128
    source.Close()
    assert not (tmp_path/'synthetic_flux.root').exists()


def test_missing_raw_candidates_are_shape_only_and_not_measured(tmp_path):
    import pytest
    from calibration.run_manifest import RunRecord, write_manifest
    from observable_extraction.calibration.flux_v2 import load_exposures
    from flux_studies.study_missing_flux import run_study
    from flux_studies.reporting import write_study
    audit=study_audit(12)
    del audit['histograms'][(6,'POL1')]
    audit['rows']=[dict(run_number=6,state='POL1',problems=['missing_raw'])]
    result=run_study(audit,mode='offline',n_splits=3,seed=42,n_replicas=3,mask_patterns=(('POL1',),))
    assert result['candidates']
    assert all(p['domain']=='shape' and p['provenance']=='synthetic' for p in result['candidates'])
    assert all(6 not in p['training_runs'] for p in result['candidates'])
    assert (6,'POL1') not in audit['histograms']
    write_study(tmp_path,audit,result)
    manifest=tmp_path/'manifest.csv'
    write_manifest([RunRecord(6,'1998_uv','P','UV','P_UV','manual','1998_uv/run6.root')],manifest)
    assert (tmp_path/'synthetic_flux.root').is_file()
    with pytest.raises(ValueError,match='no complete'):
        load_exposures(tmp_path/'synthetic_flux.root',manifest_path=manifest)
