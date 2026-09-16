#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

// gamma p -> p eta pi0 with eta -> 3pi0: 8 gamma.
//
// The SIGNAL reaction with the wrong decay. Its production is identical to
// generate_eta_pi0_dataset.C — same threshold, same phase space — and only the
// eta's decay differs. Background, because an 8-photon event that fakes the
// 4-photon topology reconstructs from the WRONG photons, and accepting it
// contaminates the eta -> 2gamma measurement.
//
// Photons are written g0..g7 rather than under named branches: the named
// convention in the signal generator exists because there the eta really does
// give exactly 2 photons. Here it gives 6, and which of them pair up is not
// something the file should assert.
void generate_eta_pi0_via_3pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double meta = 0.547862;
    const double mpi0 = 0.134977;
    const double threshold = (pow(meta + mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("eta_pi0_via_3pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "gamma p -> p eta pi0, eta -> 3pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5, g6, g7;
    int n_true_gamma = 8;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("g6",&g6); tree->Branch("g7",&g7);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.75);
        beam = SmearTaggedPhoton(Ebeam, rng);
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses3[3] = {meta, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 3, masses3)) continue;
        GenerateUnweighted(evt, rng);

        TLorentzVector eta_v   = *evt.GetDecay(0);
        TLorentzVector pi0_dir = *evt.GetDecay(1);
        proton = *evt.GetDecay(2);

        double masses3pi[3] = {mpi0, mpi0, mpi0};
        TGenPhaseSpace deta;
        if (!deta.SetDecay(eta_v, 3, masses3pi)) continue;
        GenerateUnweighted(deta, rng);

        double m2[2] = {0., 0.};
        TLorentzVector tmp[8];

        // The eta's three pi0 -> six photons.
        TGenPhaseSpace d[3];
        for (int k = 0; k < 3; k++) {
            d[k].SetDecay(*deta.GetDecay(k), 2, m2);
            GenerateUnweighted(d[k], rng);
            tmp[2*k]   = SmearPhoton(*d[k].GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
            tmp[2*k+1] = SmearPhoton(*d[k].GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        }
        // The directly produced pi0 -> two more.
        TGenPhaseSpace dpi;
        dpi.SetDecay(pi0_dir, 2, m2);
        GenerateUnweighted(dpi, rng);
        tmp[6] = SmearPhoton(*dpi.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        tmp[7] = SmearPhoton(*dpi.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());

        g0=tmp[0]; g1=tmp[1]; g2=tmp[2]; g3=tmp[3];
        g4=tmp[4]; g5=tmp[5]; g6=tmp[6]; g7=tmp[7];
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d eta_pi0_via_3pi0 events\n", Nevents);
}
