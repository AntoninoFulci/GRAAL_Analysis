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


@pytest.mark.parametrize(
    ("meson", "truth"),
    (("eta", dalitz.kin.M_ETA), ("pi0", dalitz.kin.M_PI0)),
)
def test_raw_mass_comparison_uses_only_prefit_arrays(
    monkeypatch, tmp_path, meson, truth
):
    chi2_raw = np.array([0.1, 0.2])
    bdt_raw = np.array([0.3])
    chi2 = {f"{meson}_mass_raw": chi2_raw}
    bdt = {f"{meson}_mass_raw": bdt_raw}
    histogram_inputs = []
    saved = []

    def fake_mass_hist(name, title, values, lo, hi):
        histogram_inputs.append((name, values, lo, hi))
        return _Drawable()

    monkeypatch.setattr(dalitz, "_mass_hist", fake_mass_hist)
    monkeypatch.setattr(
        dalitz, "_save", lambda canvas, out_dir, stem: saved.append(stem)
    )
    monkeypatch.setattr(dalitz.ROOT, "TCanvas", lambda *_args: _Drawable())
    monkeypatch.setattr(dalitz.ROOT, "TLegend", lambda *_args: _Drawable())
    monkeypatch.setattr(dalitz.ROOT, "TLine", lambda *_args: _Drawable())

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
