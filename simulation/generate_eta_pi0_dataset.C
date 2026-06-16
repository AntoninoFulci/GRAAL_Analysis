#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <cmath>
#include <TMath.h>

// ================================================================
// Monte Carlo generator for the gamma p -> p eta pi0 reaction,
// with eta -> gamma gamma and pi0 -> gamma gamma decays and a
// simple Gaussian detector smearing applied to the final-state
// particles.
//
// Produces a labelled dataset (true + smeared 4-vectors) intended
// for training a future ML reconstruction/identification model.
//
// Run:  root -l 'simulation/generate_eta_pi0_dataset.C(1000000)'
// ================================================================

// =========================
// Photon smearing
// =========================
TLorentzVector SmearPhoton(TLorentzVector p, TRandom3 &rng,
                           double sE, double sTheta, double sPhi) {

    double E     = p.E();
    double theta = p.Theta();
    double phi   = p.Phi();

    double E_s     = rng.Gaus(E, sE * E);     // relative (percentage) smearing
    double theta_s = rng.Gaus(theta, sTheta); // absolute smearing
    double phi_s   = rng.Gaus(phi, sPhi);     // absolute smearing

    double px = E_s * sin(theta_s) * cos(phi_s);
    double py = E_s * sin(theta_s) * sin(phi_s);
    double pz = E_s * cos(theta_s);

    return TLorentzVector(px, py, pz, E_s);
}

// =========================
// Proton smearing
// =========================
TLorentzVector SmearProton(TLorentzVector p, TRandom3 &rng, double relRes,
                           double sTheta, double sPhi) {
    double Mp = 0.938272;

    double P_s     = rng.Gaus(p.P(), relRes * p.P()); // relative (percentage) smearing
    double theta_s = rng.Gaus(p.Theta(), sTheta);     // absolute smearing
    double phi_s   = rng.Gaus(p.Phi(), sPhi);         // absolute smearing

    double px = P_s * sin(theta_s) * cos(phi_s);
    double py = P_s * sin(theta_s) * sin(phi_s);
    double pz = P_s * cos(theta_s);
    double E  = sqrt(P_s * P_s + Mp * Mp);

    return TLorentzVector(px, py, pz, E);
}

void generate_eta_pi0_dataset(int Nevents = 1000000) {

    double mp   = 0.938272;
    double meta = 0.547862;
    double mpi0 = 0.134977;
    double threshold = (pow(meta + mpi0 + mp, 2) - pow(mp, 2)) / (2 * mp);

    TRandom3 rng(0);

    TFile *fout = new TFile("eta_pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "eta pi0 MC events (true + smeared)");

    TLorentzVector beam, target;
    TLorentzVector eta, pi0, proton;
    TLorentzVector eta_gamma1, eta_gamma2, pi0_gamma1, pi0_gamma2;

    tree->Branch("beam", &beam);
    tree->Branch("target", &target);
    tree->Branch("eta", &eta);
    tree->Branch("pi0", &pi0);
    tree->Branch("proton", &proton);
    tree->Branch("eta_gamma1", &eta_gamma1);
    tree->Branch("eta_gamma2", &eta_gamma2);
    tree->Branch("pi0_gamma1", &pi0_gamma1);
    tree->Branch("pi0_gamma2", &pi0_gamma2);

    for (int i = 0; i < Nevents; i++) {

        // true beam energy used for the reaction kinematics (the "truth")
        double Ebeam = rng.Uniform(threshold, 1.55); // photon beam energy (GeV)

        beam.SetPxPyPzE(0, 0, Ebeam, Ebeam);  // true beam
        target.SetPxPyPzE(0, 0, 0, mp);

        TLorentzVector W = beam + target;

        // beam energy stored in the tree, smeared by the tagger resolution (16 MeV)
        double Ebeam_s = rng.Gaus(Ebeam, 0.016);
        beam.SetPxPyPzE(0, 0, Ebeam_s, Ebeam_s);

        double masses[3] = {meta, mpi0, mp};

        TGenPhaseSpace event;
        if (!event.SetDecay(W, 3, masses)) continue;

        event.Generate();

        eta    = *event.GetDecay(0);
        pi0    = *event.GetDecay(1);
        proton = *event.GetDecay(2);

        // =========================
        // Meson decays into 2 photons
        // =========================
        TGenPhaseSpace decay_eta;
        double m_eta_decay[2] = {0.0, 0.0};
        decay_eta.SetDecay(eta, 2, m_eta_decay);
        decay_eta.Generate();

        eta_gamma1 = *decay_eta.GetDecay(0);
        eta_gamma2 = *decay_eta.GetDecay(1);

        TGenPhaseSpace decay_pi0;
        double m_pi_decay[2] = {0.0, 0.0};
        decay_pi0.SetDecay(pi0, 2, m_pi_decay);
        decay_pi0.Generate();

        pi0_gamma1 = *decay_pi0.GetDecay(0);
        pi0_gamma2 = *decay_pi0.GetDecay(1);

        // =========================
        // Detector smearing
        // =========================

        // Photons: 10% E, 5 deg theta, 3 deg phi
        eta_gamma1 = SmearPhoton(eta_gamma1, rng, 0.10, 5 * TMath::DegToRad(), 3 * TMath::DegToRad());
        eta_gamma2 = SmearPhoton(eta_gamma2, rng, 0.10, 5 * TMath::DegToRad(), 3 * TMath::DegToRad());
        pi0_gamma1 = SmearPhoton(pi0_gamma1, rng, 0.10, 5 * TMath::DegToRad(), 3 * TMath::DegToRad());
        pi0_gamma2 = SmearPhoton(pi0_gamma2, rng, 0.10, 5 * TMath::DegToRad(), 3 * TMath::DegToRad());

        // Proton: 4% momentum, 3 deg theta, 2 deg phi
        proton = SmearProton(proton, rng, 0.04, 3 * TMath::DegToRad(), 2 * TMath::DegToRad());

        tree->Fill();
    }

    tree->Write("", TObject::kOverwrite);  // reuse the key, avoid extra ;N cycles
    fout->Close();

    printf("Generated %d events with smearing\n", Nevents);
}
