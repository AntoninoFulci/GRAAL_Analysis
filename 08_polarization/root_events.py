"""Read metadata-bearing reconstruction trees for polarization analysis."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from contracts import PolarizationContractError


@dataclass(frozen=True)
class EventSample:
    beam_energy: np.ndarray
    run_number: np.ndarray
    state_code: np.ndarray
    xstrip: np.ndarray
    proton: np.ndarray
    eta: np.ndarray
    pi0: np.ndarray


def select_vector_branches(
    available: Iterable[str], vectors: str
) -> tuple[str, str, str]:
    """Select one complete vector family; never mix raw and fitted branches."""
    branches = set(available)
    common = {"RunNumber", "Polarization", "Xstrip", "beam"}
    if vectors == "raw":
        selected = ("proton", "eta", "pi0")
        required = common | set(selected)
    elif vectors == "kinematic_fit":
        selected = ("proton_fit", "eta_fit", "pi0_fit")
        required = common | set(selected) | {"fit_converged"}
    else:
        raise PolarizationContractError("vectors must be raw or kinematic_fit")
    missing = required - branches
    if missing:
        raise PolarizationContractError(
            "reconstruction tree missing required branches: "
            + ", ".join(sorted(missing))
        )
    return selected


def _vector4(value) -> tuple[float, float, float, float]:
    return (float(value.Px()), float(value.Py()), float(value.Pz()), float(value.E()))


def _validate_file_schema(ROOT, path: Path, tree_name: str, vectors: str) -> None:
    root_file = ROOT.TFile.Open(str(path), "READ")
    if not root_file or root_file.IsZombie():
        raise PolarizationContractError(f"cannot open reconstruction ROOT file: {path}")
    try:
        tree = root_file.Get(tree_name)
        if not tree or not tree.InheritsFrom("TTree"):
            raise PolarizationContractError(
                f"ROOT file {path} lacks tree {tree_name}"
            )
        available = {branch.GetName() for branch in tree.GetListOfBranches()}
        selected = select_vector_branches(available, vectors)
        for name in ("beam", *selected):
            branch = tree.GetBranch(name)
            if branch.GetClassName() != "TLorentzVector":
                raise PolarizationContractError(
                    f"ROOT branch {name} in {path} must be TLorentzVector"
                )
        integer_fields = ["RunNumber", "Polarization"]
        if vectors == "kinematic_fit":
            integer_fields.append("fit_converged")
        for name in integer_fields:
            leaf = tree.GetLeaf(name)
            if not leaf or leaf.GetTypeName() not in {"Int_t", "UInt_t", "Long64_t", "ULong64_t"}:
                raise PolarizationContractError(
                    f"ROOT branch {name} in {path} must be integer-valued"
                )
        xstrip_leaf = tree.GetLeaf("Xstrip")
        if not xstrip_leaf or xstrip_leaf.GetTypeName() not in {
            "Float_t", "Double_t", "Int_t", "UInt_t"
        }:
            raise PolarizationContractError(
                f"ROOT branch Xstrip in {path} must be numeric"
            )
    finally:
        root_file.Close()


def read_reco_root(
    paths: Iterable[Path], *, tree_name: str, vectors: str
) -> EventSample:
    """Read selected events from ROOT; reject legacy trees without metadata."""
    files = tuple(Path(path) for path in paths)
    if not files:
        raise PolarizationContractError("at least one reconstruction ROOT file is required")
    missing_files = [str(path) for path in files if not path.is_file()]
    if missing_files:
        raise PolarizationContractError(
            "reconstruction ROOT file does not exist: " + ", ".join(missing_files)
        )
    try:
        import ROOT
    except ImportError as exc:
        raise PolarizationContractError(
            "PyROOT is required to read reconstruction files"
        ) from exc
    for path in files:
        _validate_file_schema(ROOT, path, tree_name, vectors)
    chain = ROOT.TChain(tree_name)
    for path in files:
        if chain.Add(str(path)) == 0:
            raise PolarizationContractError(
                f"cannot add ROOT tree {tree_name} from {path}"
            )
    available = {branch.GetName() for branch in chain.GetListOfBranches()}
    proton_branch, eta_branch, pi0_branch = select_vector_branches(available, vectors)
    beam_energy = []
    run_number = []
    state_code = []
    xstrip = []
    proton = []
    eta = []
    pi0 = []
    for event in chain:
        if vectors == "kinematic_fit" and int(event.fit_converged) != 1:
            continue
        beam_energy.append(float(event.beam.E()))
        run_number.append(int(event.RunNumber))
        state_code.append(int(event.Polarization))
        xstrip.append(float(event.Xstrip))
        proton.append(_vector4(getattr(event, proton_branch)))
        eta.append(_vector4(getattr(event, eta_branch)))
        pi0.append(_vector4(getattr(event, pi0_branch)))
    if not beam_energy:
        raise PolarizationContractError("reconstruction selection contains no events")
    sample = EventSample(
        beam_energy=np.asarray(beam_energy, dtype=float),
        run_number=np.asarray(run_number, dtype=int),
        state_code=np.asarray(state_code, dtype=int),
        xstrip=np.asarray(xstrip, dtype=float),
        proton=np.asarray(proton, dtype=float),
        eta=np.asarray(eta, dtype=float),
        pi0=np.asarray(pi0, dtype=float),
    )
    if any(
        not np.all(np.isfinite(values))
        for values in (
            sample.beam_energy, sample.xstrip, sample.proton, sample.eta, sample.pi0
        )
    ):
        raise PolarizationContractError("reconstruction tree contains non-finite values")
    return sample
