import json
import pytest
from calibration.run_manifest import RunRecord


def test_unknown_configuration_is_not_compatible():
    from flux_studies.metadata import compatible
    a = dict(source_period='1998_uv', target='P', beam_type='UV', state='POL1', configuration_id=None, laser_id='UV')
    assert not compatible(a, dict(a))


def test_metadata_validates_identity_time_and_exposure(tmp_path):
    from flux_studies.metadata import load_metadata
    manifest = [RunRecord(7, '1998_uv', 'P', 'UV', 'P_UV', 'manual', '1998_uv/run7.root')]
    row = dict(run_number=7, state='POL1', source='log', source_period='1998_uv', target='P', beam_type='UV', start_utc='1998-01-01T00:00:00Z', end_utc='1998-01-01T00:01:00Z', configuration_id='A', laser_id='UV')
    path = tmp_path / 'metadata.json'
    def write(records):
        path.write_text(json.dumps(dict(schema_version=1, records=records)))
    write([row])
    loaded = load_metadata(path, manifest)
    assert loaded[(7, 'POL1')]['exposure'] is None
    write([row, row])
    with pytest.raises(ValueError, match='duplicate'): load_metadata(path, manifest)
    for change in [dict(target='D'), dict(start_utc='1999-01-01T00:00:00Z'), dict(start_utc='1998-01-01T00:00:00'), dict(exposure=dict(value=-1, error=0, unit='s', definition='live'))]:
        write([{**row, **change}])
        with pytest.raises(ValueError): load_metadata(path, manifest)


@pytest.mark.parametrize('time', [42, [], {}, True])
def test_invalid_timestamp_types_are_input_errors(tmp_path,time):
    from flux_studies.metadata import load_metadata
    manifest=[RunRecord(7,'1998_uv','P','UV','P_UV','manual','1998_uv/run7.root')]
    path=tmp_path/'metadata.json'
    path.write_text(json.dumps(dict(schema_version=1,records=[dict(run_number=7,state='POL1',source='log',start_utc=time)])))
    with pytest.raises(ValueError):load_metadata(path,manifest)
