"""Safe bounded vector recovery, not arbitrary PostScript execution."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]


def extractor():
    spec = importlib.util.spec_from_file_location('fix2010_extractor', ROOT / 'scripts/extract_fix2010_helicity.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_shifted_scaled_axes_known_curve():
    m = extractor()
    # x=100..500 maps 1..1.4; y=-30..170 maps 0..2.
    # Curve rho=2*E-1 has physical vertices (1,1),(1.2,1.4),(1.4,1.8).
    paths = m.parse_body('2 setlinewidth 100 70 m 300 110 l 500 150 l s')
    x = m.AxisCalibration(((100,1.),(500,1.4)), ((300,1.2),))
    y = m.AxisCalibration(((-30,0.),(170,2.)), ((70,1.),))
    energy, rho = m.calibrate_path(paths[0], x, y)
    assert energy == pytest.approx([1.,1.2,1.4])
    assert rho == pytest.approx([1.,1.4,1.8])


@pytest.mark.parametrize('body', ['0 0 m 1 1 curveto', '0 0 m 1 1 translate', '1 1 l', '0 0 m nan 1 l', '1 2'])
def test_unsupported_postscript_rejected(body):
    m = extractor()
    with pytest.raises(ValueError): m.parse_body(body)


def test_wrong_archive_hash(tmp_path):
    m = extractor()
    source = tmp_path / 'wrong.tar.gz'
    source.write_bytes(b'not the expected archive')
    with pytest.raises(ValueError, match='archive hash'):
        m.extract_ratio(source, tmp_path/'out.json', tmp_path/'diag')
    assert not (tmp_path/'out.json').exists()


def test_wrong_member_hash():
    m = extractor()
    with pytest.raises(ValueError, match='member hash'):
        m.verify_member(b'wrong figure')


def test_real_source_reproducible_and_no_overwrite(tmp_path):
    m = extractor()
    archive = ROOT / 'docs/reference_papers/Fix_2010_1004.5240v1_source.tar.gz'
    output = tmp_path/'ratio.json'
    m.extract_ratio(archive, output, tmp_path/'diag')
    assert output.read_bytes() == (ROOT/'data/theory/fix2010/helicity_ratio_fig6_solution_i.json').read_bytes()
    with pytest.raises(FileExistsError): m.extract_ratio(archive, output, tmp_path/'diag')
