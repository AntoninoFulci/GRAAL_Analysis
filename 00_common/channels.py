"""Meson masses, two-meson hypotheses, and the MC channel registry.

The one place that knows what a channel is. Everything downstream — the
reconstruction (03), the MC bookkeeping (04), the stage-1 features and training
(05), the plots (06) — imports from here rather than restating it, because a
second copy of the eta mass or of the channel list is free to drift out of the
first, and has: the masses used to live in three modules at once, one of which
carried a comment asking the reader to keep them in sync by hand.

Two ideas that are easy to confuse, and are deliberately separate here:

  Hypothesis — WHICH TWO MESONS the 4 observed photons are being tested against.
    It sets the mass and the chi2 the features are built around. It is a
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
M_OMEGA = 0.78266
M_ETAPRIME = 0.95778

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
        Reference cross-section [ub] at `e_ref_gev`, from the paper cited below.
        The channel's weight is NOT this number: it is sigma(E) integrated over
        the measured beam flux and the detector acceptance — see
        `cross_sections.sigma_at` and `build_background_features.channel_yield`.

        Acceptance is not double-counted, and the split is worth stating because
        it was wrong for a long time. A channel's weight divides by the
        GENERATED count, not by the survivor total: generated count is
        bookkeeping (an arbitrary choice of how many events to simulate) and
        must be erased, while the survival fraction is physics (the detector's
        acceptance for this topology) and must not be. Both live in the same
        survivor count, and a renormalisation onto the survivor total erased
        them together — which weighted an 8-photon channel as though it
        reconstructed as efficiently as a 4-photon one.

        None means the cross-section is not known — which for eta_pi0 is not an
        oversight but the point of the experiment. See below.

    e_ref_gev:
        Beam energy at which `sigma_ref_ub` was measured. Given with it or not
        at all: sigma_ref alone does not say where on the excitation curve it
        sits, and the shape needs that to normalise. Must be above threshold.

    production_masses:
        Masses of the PRODUCTION final state, recoil proton included — what the
        reaction makes, before anything decays. Sets both the threshold and the
        phase-space shape of sigma(E). The decay is deliberately absent: how the
        eta later falls apart does not change how the cross-section turns on,
        which is why eta_pi0 and eta_pi0_via_3pi0 share this tuple exactly.

    signal_br_ratio:
        For a background that is the SIGNAL reaction with a different decay:
        BR(this decay) / BR(the signal's decay). Its weight is slaved to the
        signal's through this ratio instead of to a cross-section, because its
        cross-section IS the signal's and putting a number to it would be
        circular. PDG branching ratios only; no absolute cross-section appears.
        None for every ordinary background.

    hypothesis:
        The two-meson hypothesis this channel determines on its own, or None
        when it does not fix one (see the module docstring).
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
        """Beam energy at which this reaction first becomes possible.

        Derived, never stored: the .C generators compute the same quantity from
        the same masses to set their Uniform() lower edge, and a second copy
        here would be free to drift from them.
        """
        total = sum(self.production_masses)
        return (total**2 - M_PROTON**2) / (2.0 * M_PROTON)


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
# Sources (see the per-channel comments above for the reference energy each
# sigma_ref sits at, and for the estimates that are not measurements):
#   pi0pi0       : CB-ELSA/TAPS, Sarantsev et al., EPJ A 25 (2005) 441
#   3pi0         : Kashevarov et al. (A2-MAMI), PRC 85 (2012) 064610,
#                  arXiv:1101.3744 Table I  [was wrongly cited to Thoma PLB 659
#                  (2008) 87, which is a 2pi0 paper]
#   eta_2pi0     : NO dedicated measurement exists; sigma_ref is an estimate
#                  ceilinged by the eta' total (Crede et al., arXiv:0909.1248)
#   omega_pi0    : CB-ELSA/TAPS, Junkersfeld et al., EPJ A 31 (2007) 365,
#                  arXiv:0704.0710 Table 3  [was wrongly cited to Barth EPJ A 18
#                  (2003) 117, which is single-omega, not omega pi0]
#   etaprime     : CB-ELSA, Crede et al., PRC 80 (2009) 055202, arXiv:0909.1248;
#                  PDG BR(eta' -> eta pi0 pi0) = 0.228
#   eta_via_3pi0 : sigma(gamma p -> p eta) from McNicoll et al. (A2), PRC 82
#                  (2010) 035208, arXiv:1007.0777; PDG BR(eta -> 3pi0) = 0.327
#   4pi0         : NO published exclusive cross-section; sigma_ref is an
#                  order-of-magnitude upper bound scaled from 3pi0
#   eta_pi0_via_3pi0 : no cross-section by construction — slaved to the signal
#                  through PDG BR(eta->3pi0)/BR(eta->2gamma)
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
        # eta_2pi0: gamma p -> p eta pi0 pi0. NO dedicated total cross-section
        # exists in the literature (every "eta + pion" measurement is the single
        # -pi0 channel gamma p -> p pi0 eta, a different final state). 0.3 ub is
        # an ESTIMATE ceilinged by the eta' total (~1 ub, arXiv:0909.1248),
        # uncertain by a factor 2-3. It barely opens in GRAAL (threshold 1.174,
        # beam ~1.5) so its weight is near zero regardless — the imprecision does
        # not propagate. The old registry carried a made-up 0.6 ub from a wrong-
        # reaction citation; this is no worse and is now labelled as the estimate
        # it is.
        MCChannel(
            name="eta_2pi0",
            sigma_ref_ub=0.3,   # ESTIMATE, not a measurement — see comment above
            e_ref_gev=1.90,
            production_masses=(M_PROTON, M_ETA, M_PI0, M_PI0),
        ),
        # omega_pi0: near-threshold anchor from the real gamma p -> p omega pi0
        # measurement, Junkersfeld arXiv:0704.0710 Table 3 (0.49 ub in the 1383-
        # 1817 MeV bin). Not the higher-statistics 1.95 ub @ 1.92: anchoring far
        # above threshold, where resonances inflate sigma, then rescaling down by
        # PURE phase space would over-predict near threshold. The channel barely
        # opens in GRAAL (threshold 1.366, beam ~1.5) so its weight is near zero.
        # The old registry used Barth's single-omega number (1.2 ub), a different
        # reaction whose value sat BELOW this threshold — a divide-by-zero.
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
        # gamma p -> p eta with eta -> 3pi0. The largest gap in the old sample,
        # and the dangerous kind: the event holds a genuine eta, so dropping 2
        # of its 6 photons leaves 4 with a real eta mass and a real pi0 mass. It
        # lands on the signal chi2 minimum rather than in the tails. eta_2pi0
        # and etaprime are here precisely because they carry a real eta; this
        # has a larger cross-section than either and carried weight zero.
        #
        # sigma(gamma p -> p eta) swings ~16x across the GRAAL range (16 ub at
        # the S11(1535) peak, ~2 ub past it). Anchored at the local-minimum
        # landmark E_gamma=1.03 (McNicoll A2 arXiv:1007.0777: 2.0 ub) rather than
        # the peak: the saturating phase-space model plateaus and cannot fall, so
        # a peak anchor would hold sigma at its maximum across all higher energy,
        # where real sigma(eta) is dropping. 2.0 x BR(eta->3pi0) 0.327 = 0.65 ub.
        MCChannel(
            name="eta_via_3pi0",
            sigma_ref_ub=0.65,  # 2.0 ub x BR(eta -> 3pi0) 0.327
            e_ref_gev=1.03,
            production_masses=(M_PROTON, M_ETA),
        ),
        # 4pi0: gamma p -> p 4pi0. NO published exclusive total cross-section
        # exists (8-photon final state, essentially unmeasured). 0.2 ub is an
        # order-of-magnitude UPPER BOUND, scaled down from 3pi0 (~2.9 ub at 1.43
        # GeV). Opens at 0.695 but needs to lose 4 of 8 photons, so its 4-photon
        # acceptance — and therefore its weight — is small regardless.
        MCChannel(
            name="4pi0",
            sigma_ref_ub=0.2,   # ESTIMATE / upper bound, not a measurement
            e_ref_gev=1.45,
            production_masses=(M_PROTON, M_PI0, M_PI0, M_PI0, M_PI0),
        ),
        # The signal reaction with the wrong decay. Background, because an
        # 8-photon event faking 4 reconstructs from the WRONG photons, and
        # accepting it contaminates the eta -> 2gamma measurement.
        #
        # Weighted by a branching ratio, not a cross-section: its cross-section
        # is sigma(gamma p -> p eta pi0) x 0.327, and that is the number this
        # analysis exists to produce. Slaving it to the signal through
        # BR(3pi0)/BR(2gamma) cancels sigma(signal) algebraically — it appears
        # identically in numerator and denominator and never has to be named.
        MCChannel(
            name="eta_pi0_via_3pi0",
            sigma_ref_ub=None,  # would be sigma(signal) x 0.327 — circular
            e_ref_gev=None,
            production_masses=(M_PROTON, M_ETA, M_PI0),
            signal_br_ratio=0.327 / 0.394,  # PDG BR(eta->3pi0) / BR(eta->2gamma)
        ),
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
