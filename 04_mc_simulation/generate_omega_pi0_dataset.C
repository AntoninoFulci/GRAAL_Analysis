#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_omega_pi0_dataset(int Nevents = 1000000) {
    const double mp     = 0.938272;
    const double momega = 0.78265;
    const double mpi0   = 0.134977;
    const double threshold = (pow(momega + mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("omega_pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "omega pi0 background MC (omega->gamma pi0)");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4;
    int n_true_gamma = 5;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam, 0.016), rng.Gaus(Ebeam, 0.016));
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses3[3] = {momega, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 3, masses3)) continue;
        evt.Generate();

        TLorentzVector omega_v   = *evt.GetDecay(0);
        TLorentzVector outer_pi0 = *evt.GetDecay(1);
        proton = *evt.GetDecay(2);

        // omega -> gamma + pi0 (radiative decay BR 8.28%)
        double m_omega_decay[2] = {0., mpi0};
        TGenPhaseSpace domega;
        domega.SetDecay(omega_v, 2, m_omega_decay);
        domega.Generate();

        TLorentzVector omega_gamma = *domega.GetDecay(0);
        TLorentzVector omega_pi0  = *domega.GetDecay(1);

        double m2[2] = {0., 0.};
        TGenPhaseSpace dopi, dout;
        dopi.SetDecay(omega_pi0,  2, m2); dopi.Generate();
        dout.SetDecay(outer_pi0,  2, m2); dout.Generate();

        g0 = SmearPhoton(omega_gamma,        rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*dopi.GetDecay(0),  rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*dopi.GetDecay(1),  rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*dout.GetDecay(0),  rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g4 = SmearPhoton(*dout.GetDecay(1),  rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d omega+pi0 events\n", Nevents);
}
