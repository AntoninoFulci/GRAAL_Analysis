"""Tests for channel yields and training-mixture shares."""

import numpy as np
import pytest

from bdt_training.dataset.channel_weights import ChannelYield, channel_yield, compute_shares
from graal_common.physics.channels import M_ETA, M_PI0, M_PROTON, MCChannel


def _background(name, sigma=1.0, e_ref=1.2):
    return MCChannel(
        name=name,
        sigma_ref_ub=sigma,
        e_ref_gev=e_ref,
        production_masses=(M_PROTON, M_PI0, M_PI0),
    )


def _signal():
    return MCChannel(
        name="eta_pi0",
        sigma_ref_ub=None,
        e_ref_gev=None,
        production_masses=(M_PROTON, M_ETA, M_PI0),
    )


def _slaved(branching_ratio=0.830):
    return MCChannel(
        name="eta_pi0_via_3pi0",
        sigma_ref_ub=None,
        e_ref_gev=None,
        production_masses=(M_PROTON, M_ETA, M_PI0),
        signal_br_ratio=branching_ratio,
    )


class TestChannelYield:
    def test_divides_by_generated_count(self):
        channel = _background("probe")
        beam_energy = np.full(100, 1.3)
        weights = np.ones(100)

        small = channel_yield(channel, beam_energy, weights, n_gen=1000)
        large = channel_yield(channel, beam_energy, weights, n_gen=2000)

        assert large.y_sigma == pytest.approx(small.y_sigma / 2.0)

    def test_preserves_acceptance(self):
        channel = _background("probe")
        full = channel_yield(channel, np.full(400, 1.3), np.ones(400), 1000)
        half = channel_yield(channel, np.full(200, 1.3), np.ones(200), 1000)

        assert half.y_sigma == pytest.approx(full.y_sigma / 2.0)

    def test_unit_yield_ignores_cross_section(self):
        value = channel_yield(
            _background("probe", sigma=5.0),
            np.full(100, 1.3),
            np.full(100, 2.0),
            n_gen=500,
        )

        assert value.y_unit == pytest.approx(100 * 2.0 / 500)

    def test_unknown_cross_section_produces_none(self):
        value = channel_yield(
            _signal(), np.full(10, 1.3), np.ones(10), n_gen=100
        )

        assert value.y_sigma is None
        assert value.y_unit == pytest.approx(10 / 100)

    def test_zero_weighted_events_do_not_contribute(self):
        channel = _background("probe")
        weights = np.concatenate([np.ones(50), np.zeros(50)])
        half = channel_yield(channel, np.full(100, 1.3), weights, n_gen=1000)
        full = channel_yield(
            channel, np.full(50, 1.3), np.ones(50), n_gen=1000
        )

        assert half.y_sigma == pytest.approx(full.y_sigma)

    def test_refuses_non_positive_generated_count(self):
        with pytest.raises(ValueError, match="n_gen must be positive"):
            channel_yield(
                _background("probe"), np.full(10, 1.3), np.ones(10), n_gen=0
            )


class TestComputeShares:
    def _yields(self):
        signal = ChannelYield(
            _signal(), y_sigma=None, y_unit=1.0, is_signal=True
        )
        first = ChannelYield(
            _background("pi0pi0"), y_sigma=3.0, y_unit=1.0, is_signal=False
        )
        second = ChannelYield(
            _background("3pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False
        )
        return [signal, first, second]

    def test_signal_gets_exact_prior(self):
        shares = compute_shares(self._yields(), 0.5)

        assert shares["eta_pi0"] == pytest.approx(0.5)

    def test_everything_sums_to_one(self):
        shares = compute_shares(self._yields(), 0.5)

        assert sum(shares.values()) == pytest.approx(1.0)

    def test_backgrounds_split_by_yield(self):
        shares = compute_shares(self._yields(), 0.5)

        assert shares["pi0pi0"] == pytest.approx(0.5 * 0.75)
        assert shares["3pi0"] == pytest.approx(0.5 * 0.25)

    def test_slaved_channel_uses_branching_ratio_and_acceptance(self):
        signal = ChannelYield(
            _signal(), y_sigma=None, y_unit=2.0, is_signal=True
        )
        slaved = ChannelYield(
            _slaved(0.830), y_sigma=None, y_unit=0.2, is_signal=False
        )
        background = ChannelYield(
            _background("pi0pi0"), y_sigma=1.0, y_unit=1.0, is_signal=False
        )

        shares = compute_shares([signal, slaved, background], 0.5)

        assert shares["eta_pi0_via_3pi0"] == pytest.approx(0.5 * 0.830 * 0.1)

    def test_slaved_share_depends_only_on_acceptance_ratio(self):
        base = compute_shares(
            [
                ChannelYield(_signal(), None, 2.0, True),
                ChannelYield(_slaved(), None, 0.2, False),
                ChannelYield(_background("pi0pi0"), 1.0, 1.0, False),
            ],
            0.5,
        )
        doubled = compute_shares(
            [
                ChannelYield(_signal(), None, 4.0, True),
                ChannelYield(_slaved(), None, 0.4, False),
                ChannelYield(_background("pi0pi0"), 1.0, 1.0, False),
            ],
            0.5,
        )

        assert doubled["eta_pi0_via_3pi0"] == pytest.approx(
            base["eta_pi0_via_3pi0"]
        )

    def test_acceptance_keeps_slaved_share_usable(self):
        signal = ChannelYield(_signal(), None, 1.0, True)
        slaved = ChannelYield(_slaved(), None, 0.1, False)
        background = ChannelYield(_background("pi0pi0"), 1.0, 1.0, False)

        shares = compute_shares([signal, slaved, background], 0.5)

        assert shares["eta_pi0_via_3pi0"] < 0.1
        assert shares["pi0pi0"] > 0.4

    def test_refuses_prior_that_leaves_no_background_budget(self):
        values = [
            ChannelYield(_signal(), None, 1.0, True),
            ChannelYield(_slaved(0.830), None, 1.0, False),
            ChannelYield(_background("pi0pi0"), 1.0, 1.0, False),
        ]

        with pytest.raises(ValueError, match="no weight left"):
            compute_shares(values, 0.9)

    def test_refuses_prior_outside_zero_to_one(self):
        with pytest.raises(ValueError, match="strictly between 0 and 1"):
            compute_shares(self._yields(), 1.0)

    def test_refuses_multiple_signals(self):
        signal = ChannelYield(_signal(), None, 1.0, True)
        background = ChannelYield(_background("pi0pi0"), 1.0, 1.0, False)

        with pytest.raises(ValueError, match="exactly one signal"):
            compute_shares([signal, signal, background], 0.5)

    def test_refuses_signal_without_surviving_weight(self):
        signal = ChannelYield(_signal(), None, 0.0, True)
        background = ChannelYield(_background("pi0pi0"), 1.0, 1.0, False)

        with pytest.raises(ValueError, match="no weight left"):
            compute_shares([signal, background], 0.5)

    def test_refuses_backgrounds_without_yield(self):
        signal = ChannelYield(_signal(), None, 1.0, True)
        background = ChannelYield(_background("pi0pi0"), 0.0, 1.0, False)

        with pytest.raises(ValueError, match="no weight left"):
            compute_shares([signal, background], 0.5)

    def test_refuses_weightless_ordinary_background(self):
        signal = ChannelYield(_background("pi0pi0"), 1.0, 1.0, True)
        weightless = ChannelYield(_signal(), None, 1.0, False)

        with pytest.raises(ValueError, match="no cross-section to be weighted by"):
            compute_shares([signal, weightless], 0.5)
