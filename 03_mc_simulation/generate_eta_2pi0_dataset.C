#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_eta_2pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double meta = 0.547862;
    const double mpi0 = 0.134977;
    const double threshold = (pow(meta + 2*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("eta_2pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "eta 2pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5;
    int n_true_gamma = 6;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        // 1.75, not 1.55: the real beam runs to 1.72 (see beam_spectrum.py).
        // Under flux-integrated weighting a channel is credited only with the
        // flux its MC can populate, so a ceiling below the data's tail is no
        // longer cosmetic — it would understate every channel by the slice it
        // cannot reach.
        double Ebeam = rng.Uniform(threshold, 1.75);
        beam = SmearTaggedPhoton(Ebeam, rng);
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses4[4] = {meta, mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 4, masses4)) continue;
        GenerateUnweighted(evt, rng);

        TLorentzVector eta_v = *evt.GetDecay(0);
        TLorentzVector pi0a  = *evt.GetDecay(1);
        TLorentzVector pi0b  = *evt.GetDecay(2);
        proton = *evt.GetDecay(3);

        double m2[2] = {0., 0.};
        TGenPhaseSpace de, da, db;
        de.SetDecay(eta_v, 2, m2); GenerateUnweighted(de, rng);
        da.SetDecay(pi0a,  2, m2); GenerateUnweighted(da, rng);
        db.SetDecay(pi0b,  2, m2); GenerateUnweighted(db, rng);

        g0 = SmearPhoton(*de.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*de.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*da.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*da.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g4 = SmearPhoton(*db.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g5 = SmearPhoton(*db.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d eta+2pi0 events\n", Nevents);
}
