"""The channels the reconstruction can name.

The chi2 and the pairing enumeration moved to graal_common.pairing, where the
stage-1 features get them too; they are tested in 00_common/tests/test_pairing.py.
What is left here is the mapping from a channel to the branches it writes.
"""
import numpy as np

from graal_common.channels import ETA_PI0_HYP, TWO_PI0_HYP
from reconstruction import reco_physics as rp


def test_eta_pi0_labels_its_branches_after_its_mesons():
    assert rp.ETA_PI0.heavy_label == "eta"
    assert rp.ETA_PI0.light_label == "pi0"


def test_two_pi0_distinguishes_its_two_identical_mesons():
    # The branches still need different names even when the particles do not.
    assert rp.TWO_PI0.heavy_label != rp.TWO_PI0.light_label


def test_channels_carry_the_registry_hypothesis_not_a_copy():
    # A reconstruction that disagreed with the gate about the eta mass would be
    # worse than either alone, so this must be the same object, not a lookalike.
    assert rp.ETA_PI0.hypothesis is ETA_PI0_HYP
    assert rp.TWO_PI0.hypothesis is TWO_PI0_HYP


def test_invariant_mass_of_a_particle_at_rest_is_its_mass():
    assert rp.invariant_mass(np.array([0.0, 0.0, 0.0, rp.M_ETA])) == rp.M_ETA


def test_invariant_mass_reports_zero_rather_than_nan_when_m2_goes_negative():
    assert rp.invariant_mass(np.array([1.0, 0.0, 0.0, 0.5])) == 0.0
