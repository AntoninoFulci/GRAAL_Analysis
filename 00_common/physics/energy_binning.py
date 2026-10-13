"""Analysis energy grids, independent of target and laser configuration.

Tagged energies may include a resolution tail below production threshold.
MC generators remain responsible for enforcing each channel's true threshold.
"""

from dataclasses import dataclass
import json
import math
from pathlib import Path

from graal_common.physics.beam_profiles import BEAM_PROFILES, BeamProfile, get_beam_profile


@dataclass(frozen=True)
class EnergyBinning:
    edges_gev: tuple[float, ...]

    def __post_init__(self):
        edges = tuple(self.edges_gev)
        if len(edges) < 2:
            raise ValueError("energy edges must contain at least two values")
        if any(isinstance(edge, bool) or not isinstance(edge, (int, float))
               or not math.isfinite(edge) or edge <= 0 for edge in edges):
            raise ValueError("energy edges must be finite positive numbers")
        if any(high <= low for low, high in zip(edges, edges[1:])):
            raise ValueError("energy edges must be strictly increasing")
        object.__setattr__(self, "edges_gev", tuple(float(edge) for edge in edges))

    @property
    def energy_range_gev(self):
        return self.edges_gev[0], self.edges_gev[-1]

    def validate_profile(self, profile: BeamProfile):
        # Historical final bins extend slightly beyond the Compton endpoint.
        # Keep that tagged-energy padding; exposure loading rejects individual
        # strips outside the polarization domain. Every bin must have support.
        for edge in self.edges_gev[:-1]:
            profile.polarization(edge)
        if self.edges_gev[-1] > profile.energy_range_gev[-1]:
            raise ValueError("energy grid exceeds nominal Compton endpoint padding")
        return self


def load_energy_config(path):
    """Read all profiles strictly, so typos never silently select defaults."""
    if path is None:
        return {}
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or set(data) - set(BEAM_PROFILES):
        raise ValueError("energy config must map uv/vis profiles to energy_edges_gev")
    result = {}
    for name, value in data.items():
        if not isinstance(value, dict) or set(value) != {"energy_edges_gev"}:
            raise ValueError(f"{name}: expected only energy_edges_gev")
        if not isinstance(value["energy_edges_gev"], list):
            raise ValueError(f"{name}: energy_edges_gev must be an array")
        result[name] = EnergyBinning(value["energy_edges_gev"]).validate_profile(get_beam_profile(name))
    return result


def resolve_energy_binning(profile_name, edges=None, config=None):
    profile = get_beam_profile(profile_name)
    configured = load_energy_config(config)
    grid = (EnergyBinning(edges) if edges is not None else
            configured.get(profile_name, EnergyBinning(profile.energy_edges_gev)))
    return grid.validate_profile(profile)


def add_energy_arguments(parser):
    parser.add_argument("--energy-config", type=Path,
                        help="JSON mapping uv/vis to energy_edges_gev; omitted profiles keep nominal bins")
    parser.add_argument("--energy-edges", type=float, nargs="+", metavar="GEV",
                        help="energy edges for --profile; overrides energy config")


def energy_binning_from_args(args, profile_name):
    edges, config = getattr(args, "energy_edges", None), getattr(args, "energy_config", None)
    if profile_name is None:
        if edges is not None or config is not None:
            raise ValueError("custom energy binning requires --profile")
        return None
    return resolve_energy_binning(profile_name, edges, config)
