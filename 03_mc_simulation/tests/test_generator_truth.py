"""All nominal channels retain unsmeared final states for detector transport."""
from pathlib import Path
import math

import pytest

from graal_common.physics.channels import CHANNELS, M_PROTON


@pytest.mark.parametrize("channel", CHANNELS)
def test_truth_conserves_four_momentum_before_smearing(channel, tmp_path):
    ROOT = pytest.importorskip("ROOT")
    macro = Path(__file__).resolve().parents[1] / "generators" / f"generate_{channel}_dataset.C"
    if not hasattr(ROOT, macro.stem):
        assert ROOT.gROOT.LoadMacro(str(macro)) == 0
    output = tmp_path / f"{channel}_mc.root"
    getattr(ROOT, macro.stem)(10, 1.5, 1.6, str(output), 71)
    with ROOT.TFile.Open(str(output)) as source:
        tree = source.Get("mc")
        assert tree.GetBranch("beam_true"), "Unsmeared beam is required for transport"
        assert tree.GetBranch("proton_true"), "Unsmeared recoil is required for transport"
        assert source.Get("truth_schema_version").GetVal() == 1
        smeared_differs = False
        for event in tree:
            names = CHANNELS[channel].photon_branches or tuple(f"g{i}" for i in range(event.n_true_gamma))
            photons = [getattr(event, name + "_true") for name in names]
            total = ROOT.TLorentzVector(event.proton_true)
            for photon in photons:
                assert photon.E() > 0 and abs(photon.M2()) < 1.e-10
                total += photon
            expected = event.beam_true + ROOT.TLorentzVector(0, 0, 0, M_PROTON)
            for component in ("Px", "Py", "Pz", "E"):
                assert math.isclose(getattr(total, component)(), getattr(expected, component)(), abs_tol=1.e-9)
            smeared_differs |= abs(event.beam.E() - event.beam_true.E()) > 1.e-10
        assert smeared_differs
