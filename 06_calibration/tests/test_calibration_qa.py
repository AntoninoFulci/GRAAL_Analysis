import pytest


def test_qa_rejects_changed_calibrated_file(tmp_path):
    from calibration.calibration_qa import write_calibration_qa, load_calibration_qa
    root = tmp_path / 'cal.root'
    root.write_bytes(b'first')
    qa = tmp_path / 'cal.qa.json'
    write_calibration_qa(qa, root, inputs={}, coverage=[], diagnostics={})
    assert load_calibration_qa(qa, root, expected_inputs={})['coverage'] == []
    root.write_bytes(b'second')
    with pytest.raises(ValueError, match='identity'):
        load_calibration_qa(qa, root, expected_inputs={})


def test_qa_rejects_other_inputs_and_preserves_original(tmp_path):
    from calibration.calibration_qa import write_calibration_qa, load_calibration_qa
    root = tmp_path / 'cal.root'
    root.write_bytes(b'measured')
    qa = tmp_path / 'cal.qa.json'
    write_calibration_qa(qa, root, inputs={'raw': 'a'}, coverage=[], diagnostics={})
    with pytest.raises(ValueError, match='identity'):
        load_calibration_qa(qa, root, expected_inputs={'raw': 'b'})
    assert root.read_bytes() == b'measured'
