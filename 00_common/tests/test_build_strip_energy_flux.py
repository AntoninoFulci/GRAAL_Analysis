from array import array
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from graal_common.strip_energy_flux import StripEnergyFluxError

SCRIPT = Path(__file__).parents[2] / "scripts" / "build_strip_energy_flux.py"
SPEC = importlib.util.spec_from_file_location("build_strip_energy_flux_task4", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def write_h80(path: Path, entries, branches=("beam", "RunNumber", "Xstrip")):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(ROOT, vector_type)
    beam = vector()
    run_number = array("i", [0])
    xstrip = array("f", [0.0])
    if "beam" in branches:
        tree.Branch("beam", vector_type, beam)
    if "RunNumber" in branches:
        tree.Branch("RunNumber", run_number, "RunNumber/I")
    if "Xstrip" in branches:
        tree.Branch("Xstrip", xstrip, "Xstrip/F")
    for run, strip, energy in entries:
        run_number[0] = run
        xstrip[0] = strip
        beam.SetPxPyPzE(0.0, 0.0, energy, energy)
        tree.Fill()
    tree.Write()
    output.Close()


def write_flux(
    path: Path,
    runs: dict[int, dict[str, dict[int, float]]],
    *,
    bins: int = 128,
    low: float = 0.0,
    high: float = 128.0,
):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    for run, values in runs.items():
        for suffix, contents in values.items():
            histogram = ROOT.TH1D(f"run{run}_{suffix}", "", bins, low, high)
            for strip, value in contents.items():
                histogram.SetBinContent(strip, value)
            histogram.Write()
    output.Close()


def append_histogram(path: Path, name: str):
    import ROOT

    output = ROOT.TFile(str(path), "UPDATE")
    histogram = ROOT.TH1D(name, "", 128, 0.0, 128.0)
    histogram.Write()
    output.Close()


def write_flux_with_edges(path: Path, edges):
    import ROOT

    output = ROOT.TFile(str(path), "RECREATE")
    root_edges = array("d", edges)
    for suffix in ("POL1", "POL2", "BREM"):
        histogram = ROOT.TH1D(f"run7_{suffix}", "", 128, root_edges)
        histogram.Write()
    output.Close()


def test_root_adapters_read_h80_and_flux_triplet(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "pre_7.root", [(7, 12, 1.2), (7, 13, 1.3)])
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {
        "POL1": {12: 100}, "POL2": {12: 80}, "BREM": {12: 10},
    }})

    samples, h80_qa = cli.read_h80_samples(pre)
    strips, flux_qa = cli.read_flux_histograms(flux, [7])

    assert [(row.run_number, row.xstrip) for row in samples] == [
        (7, 12.0), (7, 13.0)
    ]
    assert strips[11].pol1 == pytest.approx(100.0)
    assert strips[11].brem == pytest.approx(10.0)
    assert h80_qa["entries"] == 2
    assert flux_qa["run_count"] == 1


def test_h80_reader_recursively_sorts_root_files(tmp_path):
    pre = tmp_path / "pre"
    (pre / "b").mkdir(parents=True)
    (pre / "a").mkdir()
    write_h80(pre / "b" / "second.root", [(8, 2, 1.2)])
    write_h80(pre / "a" / "first.root", [(7, 1, 1.3)])

    samples, _ = cli.read_h80_samples(pre)

    assert [row.run_number for row in samples] == [7, 8]


def test_h80_reader_rejects_no_root_files(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()

    with pytest.raises(StripEnergyFluxError, match="no ROOT files"):
        cli.read_h80_samples(pre)


def test_h80_reader_rejects_zombie_file(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    (pre / "broken.root").write_text("not a ROOT file")

    with pytest.raises(StripEnergyFluxError, match="zombie"):
        cli.read_h80_samples(pre)


def test_h80_reader_rejects_missing_tree(tmp_path):
    import ROOT

    pre = tmp_path / "pre"
    pre.mkdir()
    output = ROOT.TFile(str(pre / "missing_tree.root"), "RECREATE")
    ROOT.TH1D("other", "", 1, 0.0, 1.0).Write()
    output.Close()

    with pytest.raises(StripEnergyFluxError, match="missing h80"):
        cli.read_h80_samples(pre)


def test_h80_reader_rejects_missing_required_branch(tmp_path):
    pre = tmp_path / "pre"
    pre.mkdir()
    write_h80(pre / "missing_beam.root", [(7, 12, 1.2)], branches=("RunNumber", "Xstrip"))

    with pytest.raises(StripEnergyFluxError, match="missing branch beam"):
        cli.read_h80_samples(pre)


def test_flux_reader_rejects_missing_requested_triplet_member(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {"POL1": {}, "POL2": {}}})

    with pytest.raises(StripEnergyFluxError, match="run7_BREM"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_wrong_bin_count(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(
        flux,
        {7: {"POL1": {}, "POL2": {}, "BREM": {}}},
        bins=127,
        high=127.0,
    )

    with pytest.raises(StripEnergyFluxError, match="run7_POL1.*128 bins"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_wrong_axis_edges(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(
        flux,
        {7: {"POL1": {}, "POL2": {}, "BREM": {}}},
        low=1.0,
        high=129.0,
    )

    with pytest.raises(StripEnergyFluxError, match="run7_POL1.*x-axis edge"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_reports_nonzero_underflow_and_overflow(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {
        "POL1": {0: 2.0, 129: 3.0}, "POL2": {}, "BREM": {},
    }})

    _, qa = cli.read_flux_histograms(flux, [7])

    assert qa["underflow_overflow"] == [
        {"histogram": "run7_POL1", "underflow": 2.0, "overflow": 3.0}
    ]


def test_flux_reader_rejects_requested_run_absent(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {8: {"POL1": {}, "POL2": {}, "BREM": {}}})

    with pytest.raises(StripEnergyFluxError, match="run 7"):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_reports_complete_extra_run_and_incomplete_triplets(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {
        7: {"POL1": {}, "POL2": {}, "BREM": {}},
        8: {"POL1": {}, "POL2": {}, "BREM": {}},
        9: {"POL1": {}, "POL2": {}},
    })

    _, qa = cli.read_flux_histograms(flux, [7])

    assert qa["extra_runs"] == [8]
    assert qa["malformed_triplets"] == [
        {"run_number": 9, "missing": ["BREM"], "present": ["POL1", "POL2"]}
    ]


def test_flux_reader_rejects_duplicate_root_key_cycles(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {"POL1": {}, "POL2": {}, "BREM": {}}})
    append_histogram(flux, "run7_POL1")

    with pytest.raises(
        StripEnergyFluxError, match=r"run7_POL1.*exactly one.*found 2"
    ):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_noncanonical_run_alias(tmp_path):
    flux = tmp_path / "flux.root"
    write_flux(flux, {7: {"POL1": {}, "POL2": {}, "BREM": {}}})
    append_histogram(flux, "run007_POL1")

    with pytest.raises(
        StripEnergyFluxError, match=r"noncanonical.*run007_POL1.*run7_POL1"
    ):
        cli.read_flux_histograms(flux, [7])


def test_flux_reader_rejects_nonfinite_axis_edge(tmp_path):
    flux = tmp_path / "flux.root"
    edges = [float(edge) for edge in range(129)]
    edges[64] = float("nan")
    write_flux_with_edges(flux, edges)

    with pytest.raises(
        StripEnergyFluxError, match=r"run7_POL1.*x-axis edge 64.*finite"
    ):
        cli.read_flux_histograms(flux, [7])


def test_open_root_file_closes_truthy_zombie_before_raising(monkeypatch, tmp_path):
    class TruthyZombie:
        closed = False

        def IsZombie(self):
            return True

        def Close(self):
            self.closed = True

    zombie = TruthyZombie()
    root = SimpleNamespace(
        TFile=SimpleNamespace(Open=lambda path, mode: zombie),
    )
    monkeypatch.setattr(cli, "_import_root", lambda: root)

    with pytest.raises(StripEnergyFluxError, match="zombie"):
        cli._open_root_file(tmp_path / "broken.root")

    assert zombie.closed is True
