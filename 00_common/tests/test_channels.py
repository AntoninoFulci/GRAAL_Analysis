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

    def test_the_backgrounds_all_have_one(self):
        # They are mixed by their measured cross-sections relative to each
        # other, which is real physics the BDT should know.
        for name in CHANNEL_NAMES:
            if name != "eta_pi0":
                assert get_channel(name).sigma_ref_ub is not None

    def test_get_channel_lists_the_alternatives(self):
        with pytest.raises(KeyError, match="known channels"):
            get_channel("nope")


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
