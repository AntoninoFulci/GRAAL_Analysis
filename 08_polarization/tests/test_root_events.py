from __future__ import annotations

import pytest

from contracts import PolarizationContractError
from root_events import _stable_event_identity, select_vector_branches


BASE = {"RunNumber", "Polarization", "Xstrip", "beam", "proton", "eta", "pi0"}


def test_select_vector_branches_requires_metadata_and_requested_set():
    assert select_vector_branches(BASE, "raw") == ("proton", "eta", "pi0")
    fitted = BASE | {
        "proton_fit", "eta_fit", "pi0_fit", "fit_converged"
    }
    assert select_vector_branches(fitted, "kinematic_fit") == (
        "proton_fit", "eta_fit", "pi0_fit"
    )


def test_select_vector_branches_rejects_legacy_or_partial_fit_tree():
    with pytest.raises(PolarizationContractError, match="RunNumber"):
        select_vector_branches(BASE - {"RunNumber"}, "raw")
    with pytest.raises(PolarizationContractError, match="proton_fit"):
        select_vector_branches(BASE | {"eta_fit", "pi0_fit", "fit_converged"}, "kinematic_fit")
    with pytest.raises(PolarizationContractError, match="Xstrip"):
        select_vector_branches(BASE - {"Xstrip"}, "raw")


def test_stable_identity_uses_file_local_entry_before_selection():
    digests = ("a" * 64, "b" * 64)

    assert _stable_event_identity(digests, tree_number=0, local_entry=2) == (
        "a" * 64,
        2,
    )
    assert _stable_event_identity(digests, tree_number=1, local_entry=0) == (
        "b" * 64,
        0,
    )
