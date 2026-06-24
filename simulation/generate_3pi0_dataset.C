#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_3pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double mpi0 = 0.134977;
    const double threshold = (pow(3*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("3pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "3pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5;
    int n_true_gamma = 6;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam, 0.016), rng.Gaus(Ebeam, 0.016));
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses4[4] = {mpi0, mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 4, masses4)) continue;
        evt.Generate();

        TLorentzVector pi[3];
        pi[0] = *evt.GetDecay(0);
        pi[1] = *evt.GetDecay(1);
        pi[2] = *evt.GetDecay(2);
        proton = *evt.GetDecay(3);

        double m2[2] = {0., 0.};
        TLorentzVector tmp[6];
        TGenPhaseSpace d[3];
        for (int k = 0; k < 3; k++) {
            d[k].SetDecay(pi[k], 2, m2);
            d[k].Generate();
            tmp[2*k]   = SmearPhoton(*d[k].GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
            tmp[2*k+1] = SmearPhoton(*d[k].GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        }
        g0=tmp[0]; g1=tmp[1]; g2=tmp[2]; g3=tmp[3]; g4=tmp[4]; g5=tmp[5];
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d 3pi0 events\n", Nevents);
}
