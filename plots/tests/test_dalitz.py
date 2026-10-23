from types import SimpleNamespace

import numpy as np
import pytest

from plots import dalitz


class _Drawable:
    def __getattr__(self, _name):
        if _name in {"GetXaxis", "GetYaxis"}:
            return lambda: self
        return lambda *_args, **_kwargs: None

    def GetMaximum(self):
        return 3.0


class _Histogram:
    def __init__(self, *args):
        self.args = args
        self.filled = []

    def Fill(self, *values):
        self.filled.append(values)


def test_histogram_names_titles_and_ranges_are_stable(monkeypatch):
    created_1d = []
    created_2d = []

    def fake_th1f(*args):
        histogram = _Histogram(*args)
        created_1d.append(histogram)
        return histogram

    def fake_th2f(*args):
        histogram = _Histogram(*args)
        created_2d.append(histogram)
        return histogram

    monkeypatch.setattr(dalitz.ROOT, "TH1F", fake_th1f, raising=False)
    monkeypatch.setattr(dalitz.ROOT, "TH2F", fake_th2f, raising=False)

    dalitz._dalitz_hist("dalitz_test", "sample", np.array([1.5]), np.array([1.1]))
    dalitz._mass_hist("mass_test", "mass", np.array([0.5]), 0.3, 0.8)
    dalitz.mass2d_hist("mass2d_test", "sample", np.array([0.5]), np.array([0.13]))

    assert created_2d[0].args == (
        "dalitz_test",
        "sample;M(#eta p)  [GeV];M(#pi^{0} p)  [GeV]",
        90,
        1.0,
        2.8,
        90,
        1.0,
        2.8,
    )
    assert created_1d[0].args == ("mass_test", "mass", 100, 0.3, 0.8)
    assert created_2d[1].args == (
        "mass2d_test",
        "sample;M(#eta)  [GeV];M(#pi^{0})  [GeV]",
        90,
        0.3,
        0.8,
        90,
        0.05,
        0.25,
    )


def test_save_keeps_pdf_filename_contract(tmp_path):
    saved = []
    canvas = SimpleNamespace(SaveAs=lambda path: saved.append(path))

    dalitz._save(canvas, tmp_path, "dalitz_confronto")

    assert saved == [str(tmp_path / "dalitz_confronto.pdf")]


@pytest.mark.parametrize(
    ("meson", "truth"),
    (("eta", dalitz.kin.M_ETA), ("pi0", dalitz.kin.M_PI0)),
)
@pytest.mark.parametrize("legacy_mapping", (False, True), ids=("arrays", "legacy"))
def test_raw_mass_comparison_uses_only_prefit_arrays(
    monkeypatch, tmp_path, meson, truth, legacy_mapping
):
    chi2_raw = np.array([0.1, 0.2])
    bdt_raw = np.array([0.3])
    if legacy_mapping:
        chi2 = {f"{meson}_mass_raw": chi2_raw}
        bdt = {f"{meson}_mass_raw": bdt_raw}
    else:
        chi2 = SimpleNamespace(**{f"{meson}_mass_raw": chi2_raw})
        bdt = SimpleNamespace(**{f"{meson}_mass_raw": bdt_raw})
    histogram_inputs = []
    saved = []

    def fake_mass_hist(name, title, values, lo, hi):
        histogram_inputs.append((name, values, lo, hi))
        return _Drawable()

    monkeypatch.setattr(dalitz, "_mass_hist", fake_mass_hist)
    monkeypatch.setattr(
        dalitz, "_save", lambda canvas, out_dir, stem: saved.append(stem)
    )
    monkeypatch.setattr(
        dalitz,
        "ROOT",
        SimpleNamespace(
            TCanvas=lambda *_args: _Drawable(),
            TLegend=lambda *_args: _Drawable(),
            TLine=lambda *_args: _Drawable(),
            kGray=1,
            kAzure=1,
            kRed=1,
        ),
    )

    hists = {}
    dalitz._draw_raw_mass_comparison(
        meson, truth, chi2, bdt, tmp_path, hists
    )

    assert histogram_inputs[0][1] is chi2_raw
    assert histogram_inputs[1][1] is bdt_raw
    assert set(hists) == {
        f"massa_{meson}_chi2_raw_confronto",
        f"massa_{meson}_bdt_raw_confronto",
    }
    assert saved == [f"massa_{meson}_raw_confronto"]


def test_squared_histogram_and_normalized_clone_keep_flow_counts():
    h = dalitz._dalitz_squared_hist('test_signed_s', 'sample',
                                    np.array([-1., 3., 9.]), np.array([2., 2., 2.]))
    assert h.GetXaxis().GetTitle() == 's_{p#eta}  [GeV^{2}]'
    assert h.GetYaxis().GetTitle() == 's_{p#pi^{0}}  [GeV^{2}]'
    assert dalitz._histogram_summary(h)['all_bins'] == 3
    assert dalitz._histogram_summary(h)['flow_bins'] == 2
    normalized = dalitz._unit_area(h)
    assert dalitz._histogram_summary(normalized)['all_bins'] == pytest.approx(1)
    assert dalitz._histogram_summary(normalized)['visible_bins'] == pytest.approx(1/3)
    assert h.GetEntries() == 3
    assert dalitz._histogram_summary(h)['all_bins'] == 3
    empty = dalitz._dalitz_squared_hist('test_empty_s', 'empty', np.array([]), np.array([]))
    assert dalitz._histogram_summary(dalitz._unit_area(empty))['all_bins'] == 0
    assert 'normalizzazione n/d' in dalitz._unit_area(empty).GetTitle()


@pytest.mark.parametrize('selection', [{}, {'chi2_cut': 10.}])
def test_incomplete_provenance_never_certifies_matched_samples(selection):
    from plots.core.dalitz_metadata import compare_selections
    record = {'schema': 2, 'selection_algorithm': 'pairing_missing_mass', 'selection': selection}
    assert compare_selections(record, record).startswith('unknown_')


def test_distinct_source_trees_cannot_be_certified_as_matched():
    from plots.core.dalitz_metadata import compare_selections
    record = {'schema': 2, 'selection_algorithm': 'pairing_missing_mass', 'channel': 'eta_pi0', 'selection': {'chi2_cut': 10.},
              'inputs': [{'sha256': 'abc', 'size': 42}], 'input_tree': 'h85'}
    with pytest.raises(ValueError, match='input_tree'):
        compare_selections(record, {**record, 'input_tree': 'h80'})


@pytest.mark.parametrize('missing', ['inputs', 'channel', 'input_tree'])
def test_complete_cuts_without_population_identity_remain_unknown(missing):
    from plots.core.dalitz_metadata import compare_selections
    record = {'schema': 2, 'selection_algorithm': 'pairing_missing_mass', 'channel': 'eta_pi0', 'input_tree': 'h85',
              'inputs': [{'sha256': 'abc', 'size': 42}],
              'selection': {'chi2_cut': 10., 'chi2_resolution_relative': .08,
                            'energy_range_gev': [1.1, 1.5], 'missing_mass_window_gev': .06,
                            'partner_mass_gev': .938272, 'photons': 'first_four_of_at_least_four',
                            'protons': 'exactly_one'}}
    del record[missing]
    assert compare_selections(record, record).startswith('unknown_')
