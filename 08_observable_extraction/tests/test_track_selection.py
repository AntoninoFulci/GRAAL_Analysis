import copy
import json

import numpy as np
import pytest

from observable_extraction.tests.test_mass_comparison import sample, exposures


def raw(**changes):
    record = dict(Nass_3=4, Itipo_track=(11, 11, 11, 11), Nparf=1,
                  N_traf=2, Index_trf=(2,), Iass_trf=(1, 7), Nparf_strange=0,
                  RawSourceFile="run.root", RawSourceEntry=12)
    return dict(record, **changes)


def metadata():
    return dict(do_fit=False, channel="eta_pi0", raw_track_metadata=dict(available=True),
                selection=dict(protons="exactly_one", photons="first_four_of_at_least_four"))


def test_strict_inventory_uses_addressed_association_not_index_or_unused_candidates():
    from observable_extraction.compare_track_selection import rejection_reasons
    assert rejection_reasons(raw(), 4) == ()  # Index 2 addresses code 7, not code 2.
    assert rejection_reasons(raw(Index_trf=(1,), Iass_trf=(6, 1)), 4) == ()


@pytest.mark.parametrize("change,photons,reason", [
    (dict(Nass_3=5, Itipo_track=(11,)*5), 5, "central_not_four"),
    (dict(Nass_3=5, Itipo_track=(11, 11, 11, 11, 2)), 4, "central_not_all_neutral"),
    (dict(Nass_3=5, Itipo_track=(11, 11, 11, 11, 13)), 4, "central_not_all_neutral"),
    (dict(Nparf=2, Index_trf=(1, 2)), 4, "forward_not_one"),
    (dict(Nparf=0, Index_trf=()), 4, "forward_not_one"),
    (dict(Index_trf=(0,)), 4, "forward_zero_index"),
    (dict(Iass_trf=(7, 1)), 4, "forward_not_good_charged"),
    (dict(Iass_trf=(7, 5)), 4, "forward_not_good_charged"),
    (dict(Nparf_strange=1), 4, "forward_noise"),
])
def test_strict_veto_rejects_extra_doubtful_and_noise_tracks(change, photons, reason):
    from observable_extraction.compare_track_selection import rejection_reasons
    assert reason in rejection_reasons(raw(**change), photons)


@pytest.mark.parametrize("change,photons", [
    (dict(Index_trf=(3,)), 4),
    (dict(Nass_3=5), 4),
    ({}, 5),
])
def test_inconsistent_metadata_aborts_instead_of_becoming_physics_veto(change, photons):
    from observable_extraction.compare_track_selection import rejection_reasons
    with pytest.raises(ValueError):
        rejection_reasons(raw(**change), photons)


def test_identity_and_empty_studies_keep_exposure_and_correlated_difference():
    from observable_extraction.compare_track_selection import compare_samples
    before = sample()
    for mask in (np.ones(len(before), dtype=bool), np.zeros(len(before), dtype=bool)):
        report, arrays = compare_samples(before, before.take(mask), exposures(),
                                         {1: "p", 2: "p", 3: "p"}, [1.1, 1.3],
                                         replicas=2, seed=12)
        assert report["event_counts"] == dict(before=1200, after=int(mask.sum()))
        assert report["exposure"]["vertical"] == 3
        assert report["exposure_universe"] == [1, 2, 3]
        if mask.any():
            common = [r for r in report["rows"] if r["status"] == "both_estimable"]
            assert len(common) == 6 and all(r["delta"] == 0 for r in common)
            np.testing.assert_allclose(report["bootstrap"]["difference_covariance"], 0, atol=1e-18)
        else:
            assert report["bootstrap"]["status"] == "no_common_estimable_bins"
            assert all(r["delta"] is None for r in report["rows"])


def write_tree(path, *, meta=None, include_raw=True):
    import ROOT
    from array import array
    from graal_common.io.raw_tracks import RawTrackWriter
    f = ROOT.TFile(str(path), "RECREATE")
    t = ROOT.TTree("events", "events")
    n = array("i", [4]); run = array("i", [1])
    t.Branch("n_photons_input", n, "n_photons_input/I")
    t.Branch("RunNumber", run, "RunNumber/I")
    writer = RawTrackWriter(t) if include_raw else None
    for i, noise in enumerate((0, 1)):
        if writer:
            writer.assign(raw(Nparf_strange=noise, RawSourceEntry=i))
        t.Fill()
    t.Write()
    ROOT.TNamed("reconstruction_provenance", json.dumps(metadata() if meta is None else meta)).Write()
    f.Close()


def test_root_mask_preserves_entry_order_and_nonexclusive_reasons(tmp_path):
    from observable_extraction.compare_track_selection import read_track_mask
    path = tmp_path / "events.root"; write_tree(path)
    mask, reasons, audit = read_track_mask(path, "events")
    assert mask.tolist() == [True, False]
    assert audit["input"] == 2 and audit["kept"] == 1
    assert reasons["forward_noise"].tolist() == [False, True]


@pytest.mark.parametrize("kind", ["legacy", "no_proton_proof", "no_raw_proof"])
def test_root_reader_refuses_unproven_baseline(tmp_path, kind):
    from observable_extraction.compare_track_selection import read_track_mask
    meta = copy.deepcopy(metadata())
    if kind == "no_proton_proof": meta["selection"].pop("protons")
    if kind == "no_raw_proof": meta.pop("raw_track_metadata")
    path = tmp_path / "events.root"; write_tree(path, meta=meta, include_raw=kind != "legacy")
    with pytest.raises(ValueError):
        read_track_mask(path, "events")
