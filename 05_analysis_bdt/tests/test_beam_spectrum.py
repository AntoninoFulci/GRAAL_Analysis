"""Tests for the beam-spectrum measurement and the MC reweighting.

The point of the module is that a flat generated beam becomes the beam GRAAL
actually had. These check that it does that, and that it refuses to invent
events at energies the data never produced.
"""
import numpy as np
import pytest

from analysis_bdt.beam_spectrum import BeamSpectrum, from_energies, reweight


def _flat(rng, n, lo, hi):
    return rng.uniform(lo, hi, n)


def _peaked(rng, n):
    """Something with an edge, like a Compton spectrum: rises, then stops."""
    return np.clip(rng.triangular(0.8, 1.45, 1.5, n), 0.8, 1.5)


class TestBeamSpectrum:
    def test_the_density_integrates_to_one(self):
        rng = np.random.default_rng(0)
        s = from_energies(_flat(rng, 10_000, 0.9, 1.5))
        assert (s.density * np.diff(s.edges)).sum() == pytest.approx(1.0)

    def test_pdf_is_zero_outside_the_measured_range(self):
        rng = np.random.default_rng(1)
        s = from_energies(_flat(rng, 1000, 0.9, 1.5))
        assert s.pdf(np.array([0.1, 5.0])).tolist() == [0.0, 0.0]

    def test_pdf_is_positive_where_events_were(self):
        rng = np.random.default_rng(2)
        s = from_energies(_flat(rng, 10_000, 0.9, 1.5))
        assert np.all(s.pdf(np.array([1.0, 1.2, 1.4])) > 0)

    def test_it_refuses_an_empty_sample(self):
        # An empty spectrum would quietly reweight every MC event to zero.
        with pytest.raises(ValueError, match="no events"):
            from_energies(np.array([5.0, 6.0]))  # all outside the range

    def test_it_survives_a_round_trip_through_disk(self, tmp_path):
        rng = np.random.default_rng(3)
        s = from_energies(_peaked(rng, 5000))
        s.save(tmp_path / "beam.npz")
        back = BeamSpectrum.load(tmp_path / "beam.npz")
        np.testing.assert_array_equal(back.edges, s.edges)
        np.testing.assert_array_equal(back.density, s.density)


class TestReweight:
    def test_a_flat_sample_takes_the_shape_of_the_target(self):
        # The whole job: the generators draw flat, the experiment did not.
        rng = np.random.default_rng(4)
        target_sample = _peaked(rng, 200_000)
        target = from_energies(target_sample)
        mc = _flat(rng, 200_000, 0.8, 1.5)

        w = reweight(mc, target)

        # The reweighted MC reproduces the target's mean, not the flat one.
        assert np.average(mc, weights=w) == pytest.approx(target_sample.mean(), abs=0.02)
        assert np.average(mc) == pytest.approx(1.15, abs=0.02)  # the flat mean

    def test_reweighting_onto_its_own_spectrum_changes_nothing(self):
        rng = np.random.default_rng(6)
        mc = _flat(rng, 50_000, 0.9, 1.5)
        w = reweight(mc, from_energies(mc))
        # Same spectrum in, same out: every event equally weighted.
        assert w.std() == pytest.approx(0.0, abs=1e-9)

    def test_events_the_data_never_produced_get_zero_weight(self):
        # MC above the data's edge describes runs that did not happen. Keeping
        # them at any weight would train the model on a beam nobody had.
        # min_mc_per_bin=0 isolates this rule from the thin-MC floor, which is
        # a different reason to drop an event (see TestThresholdTail).
        rng = np.random.default_rng(7)
        target = from_energies(_flat(rng, 50_000, 0.9, 1.3))
        mc = np.array([1.0, 1.2, 1.45, 1.49])

        w = reweight(mc, target, min_mc_per_bin=0)

        assert np.all(w[:2] > 0)
        assert w[2:].tolist() == [0.0, 0.0]

    def test_the_weights_are_finite_even_where_the_mc_is_thin(self):
        rng = np.random.default_rng(8)
        target = from_energies(_peaked(rng, 100_000))
        mc = _flat(rng, 1_000, 0.8, 1.5)
        w = reweight(mc, target, min_mc_per_bin=0)
        assert np.all(np.isfinite(w))
        assert np.all(w >= 0)


class TestThresholdTail:
    """A generator draws flat from its channel's threshold, then smears.

    Below that threshold the MC holds only a smearing tail while the data is
    full of events that belong to some other channel. Dividing by the tail asks
    the MC a question it cannot answer: on the real eta_pi0 sample that bin
    returned p_data/p_mc = 1994, and 128 events ended up carrying 3.3% of all
    the training weight.
    """

    def _mc_with_a_threshold_tail(self, rng, n=200_000, threshold=0.875):
        E = rng.uniform(threshold, 1.55, n)
        return E + rng.normal(0.0, 0.016, n)  # tagger smearing

    def test_the_smearing_tail_does_not_get_a_huge_weight(self):
        rng = np.random.default_rng(9)
        # Data has plenty of events below the channel's threshold.
        target = from_energies(_flat(rng, 200_000, 0.64, 1.55))
        mc = self._mc_with_a_threshold_tail(rng)

        w = reweight(mc, target)

        # Nothing may dominate: the tail is where 1994 came from.
        assert w.max() < 50

    def test_it_keeps_most_of_the_effective_sample_size(self):
        # The failure this guards was silent — the ratios stayed correct and the
        # sample quietly became worth 1.2% of its events.
        rng = np.random.default_rng(10)
        target = from_energies(_flat(rng, 200_000, 0.64, 1.55))
        mc = self._mc_with_a_threshold_tail(rng)

        w = reweight(mc, target)
        w = w / w.mean()
        ess = w.sum() ** 2 / (w**2).sum()

        assert ess > 0.5 * len(w)

    def test_a_thin_bin_is_dropped_rather_than_amplified(self):
        rng = np.random.default_rng(11)
        target = from_energies(_flat(rng, 100_000, 0.6, 1.5))
        # One lonely event far below where the bulk of the MC lives.
        mc = np.concatenate([_flat(rng, 100_000, 1.0, 1.5), [0.65]])

        w = reweight(mc, target, min_mc_per_bin=200)

        assert w[-1] == 0.0

    def test_a_well_covered_bin_is_untouched_by_the_floor(self):
        rng = np.random.default_rng(12)
        mc = _flat(rng, 200_000, 0.9, 1.5)
        w = reweight(mc, from_energies(mc), min_mc_per_bin=200)
        # Same spectrum in and out: every bin is well populated, so the floor
        # must not bite and every event must still weigh the same.
        assert np.all(w > 0)
        assert w.std() == pytest.approx(0.0, abs=1e-9)
