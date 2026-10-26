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

// gamma p -> p 4pi0 -> 8 gamma. Must lose 4 of its 8 photons to reach the
// 4-photon topology, so its acceptance is small — which is exactly why the
// weighting has to keep the survival fraction rather than normalise it away.
void generate_4pi0_dataset(int Nevents = 1000000,
                           double requested_min_gev = -1.0,
                           double requested_max_gev = 1.75,
                           const char *output_path = "4pi0_mc.root",
                           unsigned int seed = 0) {
    if (Nevents <= 0) throw std::invalid_argument("Nevents must be positive");
    const double mp   = 0.938272;
    const double mpi0 = 0.134977;
    const double threshold = (pow(4*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);
    const BeamWindow beam_window = ResolveBeamWindow(
        threshold, requested_min_gev, requested_max_gev
    );

    const unsigned int effective_seed = ResolveGeneratorSeed(seed);
    TRandom3 rng(effective_seed);
    GeneratorRandomScope random_scope(&rng);
    TDirectory::TContext directory_scope;
    TFile fout(output_path, "RECREATE");
    if (fout.IsZombie()) throw std::runtime_error("cannot create generator output");
    TTree *tree = new TTree("mc", "4pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5, g6, g7;
    int n_true_gamma = 8;
    GeneratorTruth truth(*tree, n_true_gamma);

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("g6",&g6); tree->Branch("g7",&g7);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(beam_window.low, beam_window.high);
        truth.beam.SetPxPyPzE(0, 0, Ebeam, Ebeam);
        beam = SmearTaggedPhoton(Ebeam, rng);
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0, 0, Ebeam, Ebeam) + target;

        double masses5[5] = {mpi0, mpi0, mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 5, masses5)) continue;
        GenerateUnweighted(evt, rng);

        TLorentzVector pi[4];
        for (int k = 0; k < 4; k++) pi[k] = *evt.GetDecay(k);
        proton = *evt.GetDecay(4);

        double m2[2] = {0., 0.};
        TLorentzVector tmp[8];
        TGenPhaseSpace d[4];
        for (int k = 0; k < 4; k++) {
            d[k].SetDecay(pi[k], 2, m2);
            GenerateUnweighted(d[k], rng);
            truth.photons[2*k] = *d[k].GetDecay(0);
            tmp[2*k]   = SmearPhoton(truth.photons[2*k], rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
            truth.photons[2*k+1] = *d[k].GetDecay(1);
            tmp[2*k+1] = SmearPhoton(truth.photons[2*k+1], rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        }
        g0=tmp[0]; g1=tmp[1]; g2=tmp[2]; g3=tmp[3];
        g4=tmp[4]; g5=tmp[5]; g6=tmp[6]; g7=tmp[7];
        truth.proton = proton;
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        if (tree->Fill() < 0) throw std::runtime_error("failed to write generator event");
    }
    if (tree->Write("", TObject::kOverwrite) <= 0)
        throw std::runtime_error("failed to write generator tree");
    WriteGeneratorMetadata(fout, "generate_4pi0_dataset", seed, effective_seed,
                           Nevents, tree->GetEntries(), beam_window.low, beam_window.high);
    fout.Close();
    printf("Generated %d 4pi0 events\n", Nevents);
}
