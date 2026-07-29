"""The channels the reconstruction can name.

The chi2 and the pairing enumeration moved to graal_common.pairing, where the
stage-1 features get them too; they are tested in 00_common/tests/test_pairing.py.
What is left here is the mapping from a channel to the branches it writes.
"""
import numpy as np

from graal_common.channels import ETA_PI0_HYP, TWO_PI0_HYP
from graal_common.pairing import Pairing
from reconstruction import reco_core
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


class TestPartnerMass:
    def test_known_partners_map_to_their_masses(self):
        assert rp.partner_mass("proton") == rp.M_PROTON
        assert rp.partner_mass("neutron") == rp.M_NEUTRON
        assert rp.partner_mass("deuteron") == rp.M_DEUTERON

    def test_unknown_partner_lists_the_alternatives(self):
        import pytest
        with pytest.raises(KeyError, match="proton"):
            rp.partner_mass("antiproton")

    def test_proton_and_neutron_are_within_the_missing_mass_resolution(self):
        # ~1.3 MeV apart, far below the ~50 MeV missing-mass resolution: the cut
        # cannot tell a proton recoil from a neutron one, which is why the two
        # give the same window. Only the deuteron (twice the mass) differs.
        assert abs(rp.M_PROTON - rp.M_NEUTRON) < 0.005
        assert rp.M_DEUTERON > 1.8


class TestPassesMissingMass:
    def test_inside_the_window_is_kept(self):
        assert rp.passes_missing_mass(0.938, 0.938272, 0.06) is True
        assert rp.passes_missing_mass(0.90, 0.938272, 0.06) is True

    def test_outside_the_window_is_dropped(self):
        # The 0.917 contamination peak sits outside a +-0.06 window? No -- it is
        # inside. What a wide-enough offset drops is the genuine tail junk.
        assert rp.passes_missing_mass(0.70, 0.938272, 0.06) is False
        assert rp.passes_missing_mass(1.20, 0.938272, 0.06) is False

    def test_a_none_window_disables_the_cut(self):
        assert rp.passes_missing_mass(0.10, 0.938272, None) is True
        assert rp.passes_missing_mass(5.00, 0.938272, None) is True

    def test_a_non_positive_window_disables_the_cut(self):
        assert rp.passes_missing_mass(0.10, 0.938272, 0.0) is True
        assert rp.passes_missing_mass(5.00, 0.938272, -1.0) is True


def test_reconstruction_preserves_event_metadata(tmp_path, monkeypatch):
    import ROOT

    input_dir = tmp_path / "selected"
    input_dir.mkdir()
    input_path = input_dir / "selected.root"

    fout = ROOT.TFile(str(input_path), "RECREATE")
    tree = ROOT.TTree("h80", "h80")
    vector_type = "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >"
    vector = getattr(ROOT, vector_type)
    vector_list = ROOT.std.vector(vector_type)

    beam = vector()
    gammas = vector_list()
    protons = vector_list()
    neutrons = vector_list()
    run_number = np.zeros(1, dtype=np.int32)
    polarization = np.zeros(1, dtype=np.int32)
    xstrip = np.zeros(1, dtype=np.float32)

    tree.Branch("beam", vector_type, beam)
    tree.Branch("gammas", vector_list.__cpp_name__, gammas)
    tree.Branch("protons", vector_list.__cpp_name__, protons)
    tree.Branch("neutrons", vector_list.__cpp_name__, neutrons)
    tree.Branch("RunNumber", run_number, "RunNumber/I")
    tree.Branch("Polarization", polarization, "Polarization/I")
    tree.Branch("Xstrip", xstrip, "Xstrip/F")

    beam.SetPxPyPzE(0.0, 0.0, 1.5, 1.5)
    for px, py, pz, energy in (
        (0.10, 0.00, 0.20, 0.30),
        (-0.10, 0.00, 0.20, 0.30),
        (0.00, 0.05, 0.10, 0.15),
        (0.00, -0.05, 0.10, 0.15),
    ):
        photon = vector()
        photon.SetPxPyPzE(px, py, pz, energy)
        gammas.push_back(photon)
    recoil = vector()
    recoil.SetPxPyPzE(0.0, 0.0, 0.0, rp.M_PROTON)
    protons.push_back(recoil)
    run_number[0] = 4242
    polarization[0] = 2
    xstrip[0] = 73.0
    tree.Fill()
    tree.Write()
    fout.Close()

    monkeypatch.setattr(
        reco_core.pr,
        "best_pairing",
        lambda photons, hypothesis: (
            Pairing(heavy=(0, 1), light=(2, 3)),
            0.0,
        ),
    )

    output_path = tmp_path / "reco.root"
    cfg = reco_core.RecoConfig(
        input_dir=input_dir,
        input_tree="h80",
        output_file=output_path,
        output_tree="reco",
        do_fit=False,
        missing_mass_window=None,
    )
    assert reco_core.run_reconstruction(cfg, rp.ETA_PI0) == 1

    result = ROOT.TFile.Open(str(output_path))
    output = result.Get("reco")
    output.GetEntry(0)
    assert output.RunNumber == 4242
    assert output.Polarization == 2
    assert output.Xstrip == 73.0
    result.Close()
