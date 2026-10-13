// Optional gamma p -> p pi+ pi- phase-space sample, before detector response.
// It deliberately writes mc_truth, not the neutral training tree mc.
#include "../generators/beam_window.h"
#include "../generators/smearing.h"
#include <TDirectory.h>
#include <TFile.h>
#include <TNamed.h>
#include <TParameter.h>
#include <TTree.h>
#include <iostream>

void generate_pip_pim_truth(
    int Nevents = 100000,
    double requested_min_gev = -1.0,
    double requested_max_gev = 1.75,
    const char *output_path = "pip_pim_truth.root",
    unsigned int seed = 12345
) {
    // Charged pion mass (PDG) is distinct from the neutral registry mass.
    const double mp = 0.938272;
    const double mpi = 0.13957039;
    if (Nevents <= 0 || seed == 0) {
        throw std::invalid_argument("Nevents and deterministic seed must be positive");
    }
    if (!std::isfinite(requested_min_gev) || !std::isfinite(requested_max_gev)) {
        throw std::invalid_argument("beam energy bounds must be finite");
    }
    const double threshold = (std::pow(mp + 2 * mpi, 2) - mp * mp) / (2 * mp);
    const BeamWindow window = ResolveBeamWindow(
        threshold, requested_min_gev, requested_max_gev
    );

    TRandom3 rng(seed);
    // TGenPhaseSpace uses gRandom internally. Share the seeded stream with
    // beam sampling and rejection sampling, then restore the caller's RNG.
    struct RandomScope {
        TRandom *previous;
        explicit RandomScope(TRandom *current) : previous(gRandom) { gRandom = current; }
        ~RandomScope() { gRandom = previous; }
    } random_scope(&rng);
    TDirectory::TContext directory_scope;
    TFile output(output_path, "NEW");
    if (output.IsZombie()) {
        throw std::runtime_error("cannot create truth output; destination must not exist");
    }
    TTree tree("mc_truth", "gamma p -> p pi+ pi-; unweighted phase space; no detector response");
    TLorentzVector beam, target(0., 0., 0., mp), proton, plus, minus;
    Long64_t event_id;
    int n_true_gamma = 0;
    tree.Branch("beam_true", &beam);
    tree.Branch("target_true", &target);
    tree.Branch("proton_true", &proton);
    tree.Branch("pi_plus_true", &plus);
    tree.Branch("pi_minus_true", &minus);
    tree.Branch("event_id", &event_id, "event_id/L");
    tree.Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    double masses[3] = {mp, mpi, mpi};
    for (event_id = 0; event_id < Nevents; ++event_id) {
        const double energy = rng.Uniform(std::nextafter(window.low, window.high), window.high);
        beam.SetPxPyPzE(0., 0., energy, energy);
        TLorentzVector initial = beam + target;
        TGenPhaseSpace decay;
        if (!decay.SetDecay(initial, 3, masses)) {
            throw std::runtime_error("charged phase space is closed inside the requested window");
        }
        GenerateUnweighted(decay, rng);
        proton = *decay.GetDecay(0);
        plus = *decay.GetDecay(1);
        minus = *decay.GetDecay(2);
        if (tree.Fill() < 0) throw std::runtime_error("failed to write charged truth event");
    }
    if (tree.Write() <= 0) throw std::runtime_error("failed to write charged truth tree");
    TNamed("sample_kind", "truth-only; uniform beam and Lorentz-invariant phase space; no detector response; no cross-section normalization; vectors in GeV").Write();
    TParameter<Long64_t>("seed", seed).Write();
    TParameter<int>("n_generated", Nevents).Write();
    TParameter<double>("beam_min_gev", window.low).Write();
    TParameter<double>("beam_max_gev", window.high).Write();
    TParameter<double>("proton_mass_gev", mp).Write();
    TParameter<double>("charged_pion_mass_gev", mpi).Write();
    output.Flush();
    if (output.TestBit(TFile::kWriteError)) {
        throw std::runtime_error("I/O error writing charged truth sample");
    }
    std::cout << "Generated " << Nevents << " charged truth events in " << output_path << std::endl;
}
