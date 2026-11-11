"""PREAN input dimensions and readout identity, without detector-response claims."""
import hashlib

import pytest

from mc_simulation import legacy_calibration


@pytest.fixture
def calibration_files(tmp_path):
    contents = {
        'calib_bgo/run1321.cal': ' DATE: fixture\n TIME: fixture\n' + ''.join(
            f' {"BGO Source =":13s}{i:4d}   {i / 10:8.3f}\n' for i in range(1, 481)) + 'unused laser records\n',
        'calib_bgo/run1321.ped': ' DATE: fixture\n TIME: fixture\n Fera Offset = 3\n' + ''.join(
            f' {"Fera Pedestal =":16s}{i // 16:3d}   {i % 16:3d}   {100 + i / 10:8.3f}\n' for i in range(480)) + 'unused channels\n',
        'calib_tag/calib_1321.dat': ('1 2 3 4 5 6 7\n' * 9) + '8 9\n',
        'calib_strip/calstrip_1321.dat': ('1 2 3 4 5\n' * 15) + '94.7 88.9 103.1\n',
        'calib_barrel/calib_1321.dat': '1081 1305\n' * 32,
        'calib_wall/calib_1321.cal': '\n'.join(' '.join(str(i) for i in range(k, k+5)) for k in range(0, 660, 5)) + '\n',
    }
    for name, text in contents.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(text)
    return tmp_path


def test_reads_exact_prean_fields_preserving_readout_order(calibration_files):
    result = legacy_calibration.read_1998_calibration(calibration_files, 1321)
    assert result['bgo_source_constants'][0] == pytest.approx(.1)
    assert result['bgo_source_constants'][-1] == pytest.approx(48.)
    assert result['bgo_pedestal_by_readout'][0] == 100
    assert result['bgo_pedestal_by_readout'][-1] == pytest.approx(147.9)
    assert result['tagger_windows'][8] == (1., 2., 3., 4., 5., 6., 7.)
    assert result['tagger_timing'] == (8., 9.)
    assert result['strip_edge'] == 94.7
    assert result['strip_unused_edge_values'] == (88.9, 103.1)
    assert result['barrel_tdc_windows'] == ((1081., 1305.),) * 32
    assert result['wall']['tdc_calibration'][0] == 110
    assert result['wall']['gain_pms'][-1] == 659
    for record in result['sources']:
        assert record['sha256'] == hashlib.sha256((calibration_files / record['path']).read_bytes()).hexdigest()


@pytest.mark.parametrize('name', ['calib_tag/calib_1321.dat', 'calib_strip/calstrip_1321.dat',
                                   'calib_wall/calib_1321.cal', 'calib_bgo/run1321.ped'])
def test_missing_or_truncated_calibration_is_not_accepted(calibration_files, name):
    path = calibration_files / name
    path.write_text('')
    with pytest.raises(ValueError, match='calibration'):
        legacy_calibration.read_1998_calibration(calibration_files, 1321)


@pytest.mark.parametrize('name, old, new', [
    ('calib_bgo/run1321.cal', '   2   ', '   1   '),
    ('calib_bgo/run1321.ped', '  0     1', '  0     0'),
    ('calib_tag/calib_1321.dat', '1 2 3', 'nan 2 3'),
    ('calib_barrel/calib_1321.dat', '1081 1305', '1400 1305'),
])
def test_bad_channel_identity_or_numbers_rejected(calibration_files, name, old, new):
    path = calibration_files / name
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))
    with pytest.raises(ValueError, match='calibration'):
        legacy_calibration.read_1998_calibration(calibration_files, 1321)


@pytest.mark.parametrize('run', [True, 1321.5, 1964, -1])
def test_reader_does_not_infer_other_period_formats(calibration_files, run):
    with pytest.raises(ValueError, match='1998'):
        legacy_calibration.read_1998_calibration(calibration_files, run)


@pytest.mark.parametrize('relative,index,width', [
    ('calib_bgo/run1321.cal', 2, 25), ('calib_bgo/run1321.ped', 3, 33),
])
def test_partial_numeric_record_is_rejected(calibration_files, relative, index, width):
    path = calibration_files / relative
    lines = path.read_text().splitlines()
    lines[index] = lines[index][:width]
    path.write_text('\n'.join(lines))
    with pytest.raises(ValueError, match='calibration'):
        legacy_calibration.read_1998_calibration(calibration_files, 1321)


@pytest.mark.parametrize('relative,index,start,key', [
    ('calib_bgo/run1321.cal', 2, 21, 'bgo_source_constants'),
    ('calib_bgo/run1321.ped', 3, 29, 'bgo_pedestal_by_readout'),
])
def test_fortran_f8_3_implicit_decimal_is_preserved(calibration_files, relative, index, start, key):
    path = calibration_files / relative
    lines = path.read_text().splitlines()
    lines[index] = lines[index][:start] + '   63550'
    path.write_text('\n'.join(lines))
    result = legacy_calibration.read_1998_calibration(calibration_files, 1321)
    assert result[key][0] == pytest.approx(63.550)
