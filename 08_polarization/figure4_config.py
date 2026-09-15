"""Figure-4 layout projected from the validated canonical analysis config."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from analysis_config import AngleConfig, load_analysis_config
from contracts import PolarizationContractError


@dataclass(frozen=True)
class Figure4Config:
    energy_ranges: tuple[tuple[float, float], ...]
    mass_bins: int
    phi_bins: int
    target: str
    tree: str
    vectors: str
    orientation_signs: dict[str, int]
    angle: AngleConfig


def load_figure4_config(path: Path, repository_root: Path | None = None) -> Figure4Config:
    """Load Figure-4 layout only from a structurally validated config."""
    config_path = Path(path)
    root = Path(repository_root) if repository_root is not None else config_path.resolve().parents[2]
    config = load_analysis_config(config_path, root, require_approved=False)
    if config.sign_status != "approved":
        raise PolarizationContractError("sign convention requires two-reviewer approval")
    signs = dict(config.orientation_signs)
    if set(signs) != {"parallel", "perpendicular"} or set(signs.values()) != {-1, 1}:
        raise PolarizationContractError(
            "approved sign convention must assign opposite signs -1 and +1"
        )
    return Figure4Config(
        energy_ranges=tuple(
            (low, high)
            for low, high in zip(
                config.figure4_energy_edges_gev,
                config.figure4_energy_edges_gev[1:],
            )
        ),
        mass_bins=config.figure4_mass_bins,
        phi_bins=config.figure4_phi_bins,
        target=config.figure4_target,
        tree=config.figure4_tree,
        vectors=config.figure4_vectors,
        orientation_signs=signs,
        angle=config.angle,
    )
