#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"
#include "beam_window.h"
#include "generator_runtime.h"
#include "generator_truth.h"

void generate_pi0pi0_dataset(int Nevents = 1000000,
                             double requested_min_gev = -1.0,
                             double requested_max_gev = 1.75,
                             const char *output_path = "pi0pi0_mc.root",
                             unsigned int seed = 0) {
    if (Nevents <= 0) throw std::invalid_argument("Nevents must be positive");
    const double mp   = 0.938272;
    const double mpi0 = 0.134977;
    const double threshold = (pow(2*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);
    const BeamWindow beam_window = ResolveBeamWindow(
        threshold, requested_min_gev, requested_max_gev
    );

    const unsigned int effective_seed = ResolveGeneratorSeed(seed);
    TRandom3 rng(effective_seed);
    GeneratorRandomScope random_scope(&rng);
    TDirectory::TContext directory_scope;
    TFile fout(output_path, "RECREATE");
    if (fout.IsZombie()) throw std::runtime_error("cannot create generator output");
    TTree *tree = new TTree("mc", "pi0pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3;
    int n_true_gamma = 4;
    GeneratorTruth truth(*tree, n_true_gamma);

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0", &g0); tree->Branch("g1", &g1);
    tree->Branch("g2", &g2); tree->Branch("g3", &g3);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        // 1.75, not 1.55: the real beam runs to 1.72 (see beam_spectrum.py).
        // Under flux-integrated weighting a channel is credited only with the
        // flux its MC can populate, so a ceiling below the data's tail is no
        // longer cosmetic — it would understate every channel by the slice it
        // cannot reach.
        double Ebeam = rng.Uniform(beam_window.low, beam_window.high);
        truth.beam.SetPxPyPzE(0, 0, Ebeam, Ebeam);
        beam = SmearTaggedPhoton(Ebeam, rng);
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses3[3] = {mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 3, masses3)) continue;
        GenerateUnweighted(evt, rng);

        TLorentzVector pi0a = *evt.GetDecay(0);
        TLorentzVector pi0b = *evt.GetDecay(1);
        proton = *evt.GetDecay(2);

        double m2[2] = {0., 0.};
        TGenPhaseSpace da, db;
        da.SetDecay(pi0a, 2, m2); GenerateUnweighted(da, rng);
        db.SetDecay(pi0b, 2, m2); GenerateUnweighted(db, rng);

        truth.photons[0] = *da.GetDecay(0);
        g0 = SmearPhoton(truth.photons[0], rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        truth.photons[1] = *da.GetDecay(1);
        g1 = SmearPhoton(truth.photons[1], rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        truth.photons[2] = *db.GetDecay(0);
        g2 = SmearPhoton(truth.photons[2], rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        truth.photons[3] = *db.GetDecay(1);
        g3 = SmearPhoton(truth.photons[3], rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        truth.proton = proton;
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        if (tree->Fill() < 0) throw std::runtime_error("failed to write generator event");
    }
    if (tree->Write("", TObject::kOverwrite) <= 0)
        throw std::runtime_error("failed to write generator tree");
    WriteGeneratorMetadata(fout, "generate_pi0pi0_dataset", seed, effective_seed,
                           Nevents, tree->GetEntries(), beam_window.low, beam_window.high);
    fout.Close();
    printf("Generated %d pi0pi0 events\n", Nevents);
}
