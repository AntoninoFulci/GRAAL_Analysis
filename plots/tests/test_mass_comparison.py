from types import SimpleNamespace

import numpy as np

from plots import mass_comparison


def _arrays(offset=0.0):
    return SimpleNamespace(
        has_fit=True,
        eta_mass_raw=np.array([0.52, 0.55]) + offset,
        eta_mass=np.array([0.547, 0.548]) + offset,
        pi0_mass_raw=np.array([0.12, 0.14]) + offset,
        pi0_mass=np.array([0.135, 0.135]) + offset,
        pair_masses_raw={name: np.array([1.5, 1.6]) + offset for name in ("p_eta", "p_pi0", "eta_pi0")},
        pair_masses_fit={name: np.array([1.51, 1.61]) + offset for name in ("p_eta", "p_pi0", "eta_pi0")},
    )


def test_profile_and_common_mass_figures_use_all_five_pairs(tmp_path):
    profile = tmp_path / "uv"
    common = tmp_path / "common"
    mass_comparison.write_profile_masses(_arrays(), profile, "uv")
    mass_comparison.write_common_masses({"uv": _arrays(), "vis": _arrays(0.01)}, common)
    expected = {"eta", "pi0", "p_eta", "p_pi0", "eta_pi0"}
    assert {path.stem.removeprefix("mass_raw_fit_") for path in profile.glob("mass_raw_fit_*.pdf")} == expected
    assert {path.stem.removeprefix("mass_uv_vis_") for path in common.glob("mass_uv_vis_*.pdf")} == expected
