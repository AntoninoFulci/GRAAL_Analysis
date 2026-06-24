#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_pi0pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double mpi0 = 0.134977;
    const double threshold = (pow(2*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("pi0pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "pi0pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3;
    int n_true_gamma = 4;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0", &g0); tree->Branch("g1", &g1);
    tree->Branch("g2", &g2); tree->Branch("g3", &g3);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam, 0.016), rng.Gaus(Ebeam, 0.016));
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses3[3] = {mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 3, masses3)) continue;
        evt.Generate();

        TLorentzVector pi0a = *evt.GetDecay(0);
        TLorentzVector pi0b = *evt.GetDecay(1);
        proton = *evt.GetDecay(2);

        double m2[2] = {0., 0.};
        TGenPhaseSpace da, db;
        da.SetDecay(pi0a, 2, m2); da.Generate();
        db.SetDecay(pi0b, 2, m2); db.Generate();

        g0 = SmearPhoton(*da.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*da.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*db.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*db.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d pi0pi0 events\n", Nevents);
}
