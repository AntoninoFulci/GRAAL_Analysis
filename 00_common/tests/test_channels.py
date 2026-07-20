"""Tests for the channel registry.

The registry exists to stop two copies of the same fact from drifting apart, so
most of what is worth testing here is that it really is the only copy.
"""
import pytest

from graal_common.channels import (
    CHANNEL_NAMES,
    CHANNELS,
    ETA_PI0_HYP,
    HYPOTHESES,
    M_PROTON,
    TWO_PI0_HYP,
    channel_from_filename,
    get_channel,
    resolve_hypothesis,
)


class TestChannelFromFilename:
    def test_derives_channel_from_bare_filename(self):
        assert channel_from_filename("pi0pi0_mc.root").name == "pi0pi0"

    def test_derives_channel_from_full_path(self):
        assert channel_from_filename("/data/mc/eta_2pi0_mc.root").name == "eta_2pi0"

    def test_is_independent_of_argument_order(self):
        # The whole point: the channel comes from the name, not from where the
        # file sits in a --backgrounds list. Reordering must not change the
        # derived channel for any individual file.
        files = ["3pi0_mc.root", "pi0pi0_mc.root", "etaprime_mc.root"]
        forward = [channel_from_filename(f).name for f in files]
        backward = [channel_from_filename(f).name for f in reversed(files)]
        assert forward == ["3pi0", "pi0pi0", "etaprime"]
        assert backward == list(reversed(forward))

    def test_raises_on_unexpected_naming(self):
        with pytest.raises(ValueError, match="_mc.root"):
            channel_from_filename("pi0pi0.root")

    def test_raises_on_unknown_channel(self):
        with pytest.raises(KeyError, match="unknown channel"):
            channel_from_filename("jpsi_mc.root")


class TestRegistry:
    def test_every_channel_round_trips_through_its_filename(self):
        for name in CHANNEL_NAMES:
            channel = get_channel(name)
            assert channel_from_filename(channel.mc_filename) is channel

    def test_names_match_the_registry_keys(self):
        for key, channel in CHANNELS.items():
            assert key == channel.name

    def test_a_known_cross_section_is_positive(self):
        # A zero weight would silently drop a background from the training set
        # while still paying to generate and load it.
        for channel in CHANNELS.values():
            if channel.sigma_ref_ub is not None:
                assert channel.sigma_ref_ub > 0

    def test_the_signal_channel_has_no_cross_section(self):
        # Not an oversight: measuring sigma(gamma p -> p eta pi0) is what the
        # experiment is for. A number here would be an answer, used to weight
        # the very events the answer is extracted from. The training prior is
        # chosen explicitly instead — build_background_features --signal-prior.
        assert get_channel("eta_pi0").sigma_ref_ub is None

    def test_every_background_is_weighted_exactly_one_way(self):
        # Each background is weighted EITHER by a measured cross-section OR by
        # its branching ratio against the signal — never both, never neither.
        #
        # Both would count it twice. Neither would give it weight zero while
        # still paying to generate and load it, which is exactly the bug that
        # left eta -> 3pi0 out of the training set: the largest single gap in
        # the sample, contributing nothing, with nothing to say so.
        for name in CHANNEL_NAMES:
            channel = get_channel(name)
            if name == "eta_pi0":
                continue
            has_sigma = channel.sigma_ref_ub is not None
            has_br = channel.signal_br_ratio is not None
            assert has_sigma != has_br, (
                f"{name}: sigma_ref_ub and signal_br_ratio are alternatives; "
                f"got sigma={channel.sigma_ref_ub}, br={channel.signal_br_ratio}"
            )

    def test_a_cross_section_comes_with_the_energy_it_was_measured_at(self):
        # sigma_ref alone is not usable: the shape needs to know where on the
        # excitation curve that number was read off. One without the other is
        # half a measurement.
        for channel in CHANNELS.values():
            assert (channel.sigma_ref_ub is None) == (channel.e_ref_gev is None), (
                f"{channel.name}: sigma_ref_ub and e_ref_gev must be given "
                f"together or not at all"
            )

    def test_the_reference_energy_is_above_the_threshold(self):
        # Phi_n(W(e_ref)) is the denominator of the shape. At or below
        # threshold it is zero, and sigma(E) divides by it.
        for channel in CHANNELS.values():
            if channel.e_ref_gev is None:
                continue
            assert channel.e_ref_gev > channel.production_threshold_gev, (
                f"{channel.name}: e_ref_gev {channel.e_ref_gev} is not above "
                f"its threshold {channel.production_threshold_gev:.3f}"
            )

    def test_the_slaved_channel_carries_no_cross_section(self):
        # sigma(gamma p -> p eta pi0, eta -> 3pi0) is sigma(signal) x 0.327,
        # and sigma(signal) is the measurement. A number here would smuggle an
        # assumed answer into the events the answer comes from — the same
        # circle eta_pi0 itself is kept out of.
        slaved = get_channel("eta_pi0_via_3pi0")
        assert slaved.sigma_ref_ub is None
        assert slaved.e_ref_gev is None
        assert slaved.signal_br_ratio == pytest.approx(0.327 / 0.394, rel=1e-3)

    def test_get_channel_lists_the_alternatives(self):
        with pytest.raises(KeyError, match="known channels"):
            get_channel("nope")


class TestProductionStates:
    def test_every_channel_declares_at_least_two_bodies(self):
        for channel in CHANNELS.values():
            assert len(channel.production_masses) >= 2, channel.name

    def test_every_production_state_contains_a_proton(self):
        # Every channel here is gamma p -> p X. A production state without the
        # recoil proton would put the threshold and the phase space both wrong.
        for channel in CHANNELS.values():
            assert M_PROTON in channel.production_masses, channel.name

    def test_thresholds_match_the_generators(self):
        # These constants are duplicated in the .C generators, which draw
        # Uniform(threshold, 1.75). The registry derives them instead of
        # storing them, and this pins the derivation to the values the
        # generators independently compute.
        expected = {
            "eta_pi0": 0.931,
            "pi0pi0": 0.309,
            "3pi0": 0.492,
            "eta_2pi0": 1.174,
            "omega_pi0": 1.366,
            "etaprime": 1.447,
            "eta_via_3pi0": 0.708,
            "4pi0": 0.695,
            "eta_pi0_via_3pi0": 0.931,
        }
        for name, want in expected.items():
            got = get_channel(name).production_threshold_gev
            assert got == pytest.approx(want, abs=0.001), f"{name}: {got:.3f}"

    def test_the_decay_does_not_change_the_production_state(self):
        # eta_pi0 and eta_pi0_via_3pi0 are the SAME reaction; they differ only
        # in how the eta decays. sigma(E) depends on production alone, so their
        # thresholds and phase space must be identical.
        assert (
            get_channel("eta_pi0").production_masses
            == get_channel("eta_pi0_via_3pi0").production_masses
        )

    def test_the_new_channels_are_registered(self):
        for name in ("eta_via_3pi0", "4pi0", "eta_pi0_via_3pi0"):
            assert name in CHANNELS


class TestHypotheses:
    def test_heavy_is_not_lighter_than_light(self):
        for hyp in HYPOTHESES.values():
            assert hyp.heavy_mass >= hyp.light_mass

    def test_eta_pi0_is_not_degenerate(self):
        assert not ETA_PI0_HYP.is_degenerate

    def test_two_pi0_is_degenerate(self):
        # Which is what tells the reconstruction there is no heavier pair to
        # pick out, without anyone setting a flag by hand.
        assert TWO_PI0_HYP.is_degenerate


class TestResolveHypothesis:
    def test_a_channel_that_fixes_one_needs_no_help(self):
        assert resolve_hypothesis(get_channel("eta_pi0")) is ETA_PI0_HYP
        assert resolve_hypothesis(get_channel("pi0pi0")) is TWO_PI0_HYP

    def test_a_channel_that_fixes_none_refuses_to_guess(self):
        # 3pi0 seen as 4 photons is two visible pi0 out of three: which pair is
        # the signal is a choice. Guessing here would produce features that look
        # fine and mean nothing.
        with pytest.raises(ValueError, match="does not determine"):
            resolve_hypothesis(get_channel("3pi0"))

    def test_an_override_answers_for_it(self):
        assert resolve_hypothesis(get_channel("3pi0"), "eta_pi0") is ETA_PI0_HYP

    def test_an_override_wins_over_the_channel_default(self):
        assert resolve_hypothesis(get_channel("eta_pi0"), "2pi0") is TWO_PI0_HYP

    def test_an_unknown_override_is_refused(self):
        with pytest.raises(KeyError, match="unknown hypothesis"):
            resolve_hypothesis(get_channel("eta_pi0"), "eta_omega")
