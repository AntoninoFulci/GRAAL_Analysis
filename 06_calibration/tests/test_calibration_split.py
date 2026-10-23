"""Numerical and native resource contracts across the calibration ownership split."""
import importlib
import importlib.util
from pathlib import Path
import shutil

import pytest

from calibration import calibration_cache, calibrated_flux_root, strip_energy_root
from calibration.strip_energy_flux import CalibrationCell, CalibrationEnergyBin
from calibration.tests.test_build_strip_energy_flux import SCRIPT, write_h80


def test_binary_exact_cells_and_lookup_equal_across_threads(tmp_path):
    entries = [(7, pol, strip + offset, 0.75 + strip / 256 + delta)
               for pol in (0, 1, 2) for strip in range(1, 129)
               for offset, delta in ((0.0, -1 / 1024), (0.5, 1 / 1024))]
    write_h80(tmp_path / 'h80.root', entries)
    lookups, results = [], []
    for threads in (1, 4):
        lookups.append(strip_energy_root.read_h80_lookup(
            tmp_path, run_numbers=[7], samples_per_run_strip=256,
            threads=threads, progress_every_events=0))
        results.append(strip_energy_root.read_calibration_cells(
            tmp_path, run_numbers=[7], threads=threads))
    assert lookups[0] == lookups[1]
    assert results[0] == results[1]
    cells, bins = results[0]
    assert len(cells) == 384 and len(bins) == 768
    assert cells[0] == CalibrationCell(7, 0, 1, 2, 1.25, 0.75 + 1 / 256)
    assert all(isinstance(row, CalibrationEnergyBin) for row in bins)
    assert sum(row.event_count for row in bins) == 768
    import ROOT
    for pol, suffix in ((0, 'BREM'), (1, 'POL1'), (2, 'POL2')):
        histogram, profile, fit, edges = calibrated_flux_root._fit_calibration_group(
            ROOT, 7, suffix, [row for row in cells if row.polarization == pol],
            [row for row in bins if row.polarization == pol])
        assert len(edges) == 129
        assert edges == pytest.approx([0.75 + (0.5 + i) / 256 for i in range(129)], abs=1e-12)
        assert [fit.GetParameter(i) for i in range(5)] == pytest.approx([0.75, 1 / 256, 0, 0, 0], abs=1e-12)
        assert all(profile.GetBinEntries(i) == 2 for i in range(1, 129))
        assert histogram.Integral() == 256


def test_native_declaration_once_across_aliases_and_reload(tmp_path, monkeypatch):
    import ROOT
    strip_energy_root._declare_rdataframe_helpers(ROOT)
    # Once compiled, every alternate module instance must bypass Declare.
    def forbidden(*args):
        pytest.fail('Cling helper was declared more than once')
    monkeypatch.setattr(ROOT.gInterpreter, 'Declare', forbidden)
    path = Path(strip_energy_root.__file__)
    for name in ('calibration_alias_a', 'calibration_alias_b'):
        spec = importlib.util.spec_from_file_location(name, path)
        alias = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(alias)
        alias._declare_rdataframe_helpers(ROOT)
    importlib.reload(strip_energy_root)._declare_rdataframe_helpers(ROOT)
    assert ROOT.GraalStripEnergyRDF


def test_native_header_bytes_invalidate_actual_cache_identity(tmp_path, monkeypatch):
    import calibration
    before = calibration_cache.implementation_identity(SCRIPT)
    native = [row for row in before if row['source'] == 'calibration/native/strip_energy_rdf.hxx']
    assert len(native) == 1 and len(native[0]['sha256']) == 64
    package = Path(calibration.__file__).parent
    moved = tmp_path / 'calibration'
    shutil.copytree(package, moved, ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    monkeypatch.setattr(calibration, '__file__', str(moved / '__init__.py'))
    assert calibration_cache.implementation_identity(SCRIPT) == before
    header = moved / 'native/strip_energy_rdf.hxx'
    header.write_bytes(header.read_bytes() + b'\n// cache mutation\n')
    after = calibration_cache.implementation_identity(SCRIPT)
    assert calibration_cache.content_key({'implementation': before}) != calibration_cache.content_key({'implementation': after})
    header.unlink()
    with pytest.raises(ValueError, match='missing installed calibration native resource'):
        calibration_cache.implementation_identity(SCRIPT)
