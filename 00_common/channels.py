"""Registry of MC channels, particle masses, and two-meson hypotheses.

Single source of truth for all downstream modules (reconstruction, BDT training, plots).

Two independent concepts:
  Hypothesis: Which two mesons the 4 observed photons are tested against.
  MCChannel: Which reaction the MC file was generated from.

These are orthogonal: channels may or may not determine their hypothesis. When a
channel doesn't fix one, the caller must specify it explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# PDG masses [GeV].
M_PI0 = 0.134977
M_ETA = 0.547862
M_PROTON = 0.938272
M_NEUTRON = 0.939565
M_DEUTERON = 1.875613
M_OMEGA = 0.78266
M_ETAPRIME = 0.95778

# GRAAL tagger resolution. Experimental references quote 16 MeV FWHM, while
# Gaussian generators and covariance matrices require one standard deviation.
TAGGER_FWHM_GEV = 0.016
FWHM_TO_SIGMA = 1.0 / 2.3548200450309493
TAGGER_SIGMA_GEV = TAGGER_FWHM_GEV * FWHM_TO_SIGMA

# The chi2 assumes a mass resolution of 8% of the target mass.
CHI2_RESOLUTION = 0.08


@dataclass(frozen=True)
class Hypothesis:
    """Two mesons the four observed photons are tested against.

    `heavy` is the more massive of the two.
    """

    name: str
    heavy_label: str
    light_label: str
    heavy_mass: float
    light_mass: float
    # Half-width of the window used to count pairs sitting near each pole.
    # Wider for the eta because the mass resolution scales with the mass.
    heavy_window: float
    light_window: float

    @property
    def is_degenerate(self) -> bool:
        """True when both mesons are the same particle."""
        return self.heavy_mass == self.light_mass


ETA_PI0_HYP = Hypothesis(
    name="eta_pi0",
    heavy_label="eta",
    light_label="pi0",
    heavy_mass=M_ETA,
    light_mass=M_PI0,
    heavy_window=0.080,
    light_window=0.040,
)

TWO_PI0_HYP = Hypothesis(
    name="2pi0",
    heavy_label="pi0_1",
    light_label="pi0_2",
    heavy_mass=M_PI0,
    light_mass=M_PI0,
    heavy_window=0.040,
    light_window=0.040,
)

HYPOTHESES: dict[str, Hypothesis] = {h.name: h for h in (ETA_PI0_HYP, TWO_PI0_HYP)}


_MC_FILE_SUFFIX = "_mc.root"


@dataclass(frozen=True)
class MCChannel:
    """One generated reaction, as it exists on disk.

    photon_branches:
        The named photon branches, when the generator wrote them. None means the
        file uses the g0..gN convention with count from the `n_true_gamma` branch.

    sigma_ref_ub:
        Reference cross-section [ub] at `e_ref_gev`. The channel's weight is
        sigma(E) integrated over the measured beam flux and detector acceptance.
        None means the cross-section is not known.

    e_ref_gev:
        Beam energy at which `sigma_ref_ub` was measured. Must be above threshold.

    production_masses:
        Masses of the PRODUCTION final state, recoil proton included. Sets both
        the threshold and phase-space shape of sigma(E).

    signal_br_ratio:
        For a background with a different decay: BR(this decay) / BR(the signal's decay).
        Its weight is slaved to the signal's through this ratio. None for ordinary
        backgrounds.

    hypothesis:
        The two-meson hypothesis this channel determines on its own, or None when it
        does not fix one.
    """

    name: str
    sigma_ref_ub: float | None
    e_ref_gev: float | None
    production_masses: tuple[float, ...]
    photon_branches: tuple[str, ...] | None = None
    hypothesis: Hypothesis | None = None
    signal_br_ratio: float | None = None

    @property
    def mc_filename(self) -> str:
        return f"{self.name}{_MC_FILE_SUFFIX}"

    @property
    def production_threshold_gev(self) -> float:
        """Beam energy at which this reaction first becomes possible."""
        total = sum(self.production_masses)
        return (total**2 - M_PROTON**2) / (2.0 * M_PROTON)


# eta_pi0: no cross-section (it is the measurement target).
# Other channels use measured cross-sections or branching ratios.
CHANNELS: dict[str, MCChannel] = {
    c.name: c
    for c in (
        MCChannel(
            name="eta_pi0",
            sigma_ref_ub=None,  # the measurement, not an input
            e_ref_gev=None,
            production_masses=(M_PROTON, M_ETA, M_PI0),
            photon_branches=("eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"),
            hypothesis=ETA_PI0_HYP,
        ),
        MCChannel(
            name="pi0pi0",
            sigma_ref_ub=4.5,
            e_ref_gev=2.2,  # high-E tail; sigma(2pi0) peaks ~10 ub near 0.9 GeV
            production_masses=(M_PROTON, M_PI0, M_PI0),
            hypothesis=TWO_PI0_HYP,
        ),
        MCChannel(
            name="3pi0",
            sigma_ref_ub=1.8,
            e_ref_gev=1.26,  # Kashevarov arXiv:1101.3744 Table I: 1.808 ub @ 1255 MeV
            production_masses=(M_PROTON, M_PI0, M_PI0, M_PI0),
        ),
        # eta_2pi0: ESTIMATE (no dedicated measurement exists)
        MCChannel(
            name="eta_2pi0",
            sigma_ref_ub=0.3,   # ESTIMATE
            e_ref_gev=1.90,
            production_masses=(M_PROTON, M_ETA, M_PI0, M_PI0),
        ),
        # omega_pi0: near-threshold anchor, Junkersfeld et al. arXiv:0704.0710
        MCChannel(
            name="omega_pi0",
            sigma_ref_ub=0.49,
            e_ref_gev=1.60,
            production_masses=(M_PROTON, M_OMEGA, M_PI0),
        ),
        MCChannel(
            name="etaprime",
            sigma_ref_ub=0.35,
            e_ref_gev=1.6,  # Crede arXiv:0909.1248; opens 1.447, a knife-edge in GRAAL
            production_masses=(M_PROTON, M_ETAPRIME),
        ),
        # eta_via_3pi0: McNicoll et al. arXiv:1007.0777; 2.0 ub x BR(eta->3pi0)
        MCChannel(
            name="eta_via_3pi0",
            sigma_ref_ub=0.65,
            e_ref_gev=1.03,
            production_masses=(M_PROTON, M_ETA),
        ),
        # 4pi0: no published measurement; upper bound estimate from 3pi0
        MCChannel(
            name="4pi0",
            sigma_ref_ub=0.2,   # ESTIMATE / upper bound
            e_ref_gev=1.45,
            production_masses=(M_PROTON, M_PI0, M_PI0, M_PI0, M_PI0),
        ),
        # eta_pi0_via_3pi0: signal reaction with wrong decay; weighted by BR ratio
        MCChannel(
            name="eta_pi0_via_3pi0",
            sigma_ref_ub=None,
            e_ref_gev=None,
            production_masses=(M_PROTON, M_ETA, M_PI0),
            signal_br_ratio=0.327 / 0.394,  # PDG BR(eta->3pi0) / BR(eta->2gamma)
        ),
    )
}

# Generation order, which is also the order mc_status reports them in.
CHANNEL_NAMES: list[str] = list(CHANNELS)


def get_channel(name: str) -> MCChannel:
    """Return the MCChannel with the given name.

    Raises KeyError with a list of known channels if not found.
    """
    try:
        return CHANNELS[name]
    except KeyError:
        # Re-raise with helpful message showing available options
        raise KeyError(
            f"unknown channel {name!r}; known channels: {sorted(CHANNELS)}"
        ) from None


def channel_from_filename(path: str | Path) -> MCChannel:
    """Extract channel name from MC filename and return the corresponding MCChannel.

    Expected format: <channel>_mc.root. Fails if the filename doesn't match.
    """
    stem = Path(path).name
    if not stem.endswith(_MC_FILE_SUFFIX):
        raise ValueError(
            f"MC file {str(path)!r} does not match the expected "
            f"'<channel>{_MC_FILE_SUFFIX}' naming convention"
        )
    # Strip the suffix to extract the channel name
    channel_name = stem[: -len(_MC_FILE_SUFFIX)]
    return get_channel(channel_name)


def resolve_hypothesis(channel: MCChannel, override: str | None = None) -> Hypothesis:
    """Return the two-meson hypothesis to test against.

    Args:
        channel: The MCChannel defining the generated reaction.
        override: If provided, use this hypothesis name instead of the channel's default.

    Returns the override if given, otherwise returns channel.hypothesis if it is set.
    Raises ValueError if neither provides a hypothesis.
    """
    # Explicit override takes precedence
    if override is not None:
        try:
            return HYPOTHESES[override]
        except KeyError:
            raise KeyError(
                f"unknown hypothesis {override!r}; known: {sorted(HYPOTHESES)}"
            ) from None

    # Use the channel's built-in hypothesis, or fail if it doesn't have one
    if channel.hypothesis is None:
        raise ValueError(
            f"channel {channel.name!r} does not determine a two-meson hypothesis "
            f"on its own: observed as 4 photons it is an incomplete final state, "
            f"so which pair counts as the signal is a choice, not a fact. "
            f"Pass one explicitly (known: {sorted(HYPOTHESES)})."
        )
    return channel.hypothesis
