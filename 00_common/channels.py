"""Meson masses, two-meson hypotheses, and the MC channel registry.

The one place that knows what a channel is. Everything downstream — the
reconstruction (03), the MC bookkeeping (04), the stage-1 features and training
(05), the plots (06) — imports from here rather than restating it, because a
second copy of the eta mass or of the channel list is free to drift out of the
first, and has: the masses used to live in three modules at once, one of which
carried a comment asking the reader to keep them in sync by hand.

Two ideas that are easy to confuse, and are deliberately separate here:

  Hypothesis — WHICH TWO MESONS the 4 observed photons are being tested against.
    It sets the mass poles and the chi2 the features are built around. It is a
    question asked of an event, not a property the event has.

  MCChannel — WHICH REACTION a Monte Carlo file was generated from: its photon
    layout on disk and its reference cross-section. It is a property of the
    file, and says nothing on its own about how the event will be tested.

The stage-1 BDT needs both, and they are independent knobs. Any of the six
channels can be the signal class; only some of them fix a hypothesis on their
own. gamma p -> p 3pi0 seen as 4 photons is two visible pi0 out of three, and
which pair is "the signal" is not something the channel answers, so those
channels leave `hypothesis` at None and the caller must say what is being
tested.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# PDG masses [GeV].
M_PI0 = 0.134977
M_ETA = 0.547862
M_PROTON = 0.938272

# The chi2 assumes a mass resolution of 8% of the target mass.
CHI2_RESOLUTION = 0.08


@dataclass(frozen=True)
class Hypothesis:
    """Two mesons the four observed photons are tested against.

    `heavy` is the more massive of the two, which is what lets the
    reconstruction decide which pair is which. For 2pi0 the two are equal and
    that decision is meaningless, hence `is_degenerate`.
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
        """True when both mesons are the same particle (2pi0)."""
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
        The named photon branches, when the generator wrote them (the eta pi0
        generator does). None means the file uses the g0..gN convention, and
        the count comes from its own `n_true_gamma` branch at read time — the
        file is the authority on how many photons it made, not this table.

    sigma_ref_ub:
        Reference cross-section [ub], used to weight the channel in training.
        NOT multiplied by any survival fraction: the sample handed to the BDT
        has already been through the photon-loss model, so folding a survival
        estimate in here as well would count detector acceptance twice.

        None means the cross-section is not known — which for eta_pi0 is not an
        oversight but the point of the experiment. See below.

    hypothesis:
        The two-meson hypothesis this channel determines on its own, or None
        when it does not fix one (see the module docstring).
    """

    name: str
    sigma_ref_ub: float | None
    photon_branches: tuple[str, ...] | None = None
    hypothesis: Hypothesis | None = None

    @property
    def mc_filename(self) -> str:
        return f"{self.name}{_MC_FILE_SUFFIX}"


# eta_pi0 has no cross-section here, and must not be given one. Measuring
# sigma(gamma p -> p eta pi0) is what this analysis is for: a number put here
# would be an answer, borrowed from someone else or invented, used to weight the
# events the answer is extracted from. That is circular, and the circle closes
# quietly — the training would simply produce whatever prior it was handed.
#
# The five backgrounds do have measured cross-sections, and their RELATIVE sizes
# are real physics that the training should know: they say how much of the
# contamination is pi0pi0 rather than etaprime. What the numbers cannot say is
# how much signal there is relative to all of it. That ratio is a training
# choice, made explicitly in build_background_features, not a measurement.
#
# Sources:
#   pi0pi0   : CB-ELSA/TAPS, Sarantsev et al., EPJ A 25 (2005) 441
#   3pi0     : CB-ELSA/TAPS, Thoma et al., PLB 659 (2008) 87
#   eta_2pi0 : CB-ELSA, Kashevarov et al., PRL 118 (2017) 212001
#   omega_pi0: SAPHIR, Barth et al., EPJ A 18 (2003) 117
#   etaprime : CB-ELSA, Crede et al., PRC 80 (2009) 055202;
#              PDG BR(eta' -> eta pi0 pi0) = 0.228
CHANNELS: dict[str, MCChannel] = {
    c.name: c
    for c in (
        MCChannel(
            name="eta_pi0",
            sigma_ref_ub=None,  # the measurement, not an input
            photon_branches=("eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"),
            hypothesis=ETA_PI0_HYP,
        ),
        MCChannel(name="pi0pi0", sigma_ref_ub=4.5, hypothesis=TWO_PI0_HYP),
        MCChannel(name="3pi0", sigma_ref_ub=1.8),
        MCChannel(name="eta_2pi0", sigma_ref_ub=0.6),
        MCChannel(name="omega_pi0", sigma_ref_ub=1.2),
        MCChannel(name="etaprime", sigma_ref_ub=0.35),
    )
}

# Generation order, which is also the order mc_status reports them in.
CHANNEL_NAMES: list[str] = list(CHANNELS)


def get_channel(name: str) -> MCChannel:
    """Look a channel up by name, listing the alternatives when it is unknown."""
    try:
        return CHANNELS[name]
    except KeyError:
        raise KeyError(
            f"unknown channel {name!r}; known channels: {sorted(CHANNELS)}"
        ) from None


def channel_from_filename(path: str | Path) -> MCChannel:
    """Resolve a channel from its MC filename, e.g. pi0pi0_mc.root -> pi0pi0.

    The channel MUST come from the filename, never from list position: binding
    by position let an innocent reordering of --backgrounds silently pair a
    file with the wrong cross-section weight with no error at all.
    """
    stem = Path(path).name
    if not stem.endswith(_MC_FILE_SUFFIX):
        raise ValueError(
            f"MC file {str(path)!r} does not match the expected "
            f"'<channel>{_MC_FILE_SUFFIX}' naming convention"
        )
    return get_channel(stem[: -len(_MC_FILE_SUFFIX)])


def resolve_hypothesis(channel: MCChannel, override: str | None = None) -> Hypothesis:
    """The hypothesis to build features around, given the signal channel.

    Fails rather than guessing when the channel does not fix one and the caller
    did not say: a wrong hypothesis produces features that look perfectly
    reasonable and mean nothing.
    """
    if override is not None:
        try:
            return HYPOTHESES[override]
        except KeyError:
            raise KeyError(
                f"unknown hypothesis {override!r}; known: {sorted(HYPOTHESES)}"
            ) from None

    if channel.hypothesis is None:
        raise ValueError(
            f"channel {channel.name!r} does not determine a two-meson hypothesis "
            f"on its own: observed as 4 photons it is an incomplete final state, "
            f"so which pair counts as the signal is a choice, not a fact. "
            f"Pass one explicitly (known: {sorted(HYPOTHESES)})."
        )
    return channel.hypothesis
