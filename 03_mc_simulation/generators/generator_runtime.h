#pragma once

#include <TDirectory.h>
#include <TFile.h>
#include <TNamed.h>
#include <TParameter.h>
#include <TRandom3.h>
#include <TROOT.h>
#include <limits>
#include <stdexcept>

// Seed zero retains the legacy automatic-seed interface, but resolves to one
// explicit seed before constructing the generator RNG so the run can be replayed.
inline unsigned int ResolveGeneratorSeed(unsigned int requested) {
    if (requested != 0) return requested;
    TRandom3 entropy(0);
    return 1u + entropy.Integer(std::numeric_limits<unsigned int>::max());
}

// TGenPhaseSpace draws from gRandom. The beam, decays, accept/reject and detector
// smearing must share the same seeded stream. Parallelism is across processes.
class GeneratorRandomScope {
    TRandom *previous_;
public:
    explicit GeneratorRandomScope(TRandom *current) : previous_(gRandom) {
        gRandom = current;
    }
    ~GeneratorRandomScope() { gRandom = previous_; }
    GeneratorRandomScope(const GeneratorRandomScope &) = delete;
    GeneratorRandomScope &operator=(const GeneratorRandomScope &) = delete;
};

inline void WriteGeneratorMetadata(
    TFile &output, const char *generator, unsigned int requested_seed,
    unsigned int seed, int requested_events, Long64_t generated_events,
    double beam_min, double beam_max
) {
    output.cd();
    TNamed("generator", generator).Write();
    TNamed("sampling", "accept-reject-unweighted; TRandom3 shared with TGenPhaseSpace").Write();
    TNamed("root_version", gROOT->GetVersion()).Write();
    TParameter<int>("generator_schema_version", 1).Write();
    TParameter<Long64_t>("requested_seed", requested_seed).Write();
    TParameter<Long64_t>("seed", seed).Write();
    TParameter<int>("n_requested", requested_events).Write();
    TParameter<Long64_t>("n_generated", generated_events).Write();
    TParameter<double>("beam_min_gev", beam_min).Write();
    TParameter<double>("beam_max_gev", beam_max).Write();
    output.Flush();
    if (output.TestBit(TFile::kWriteError)) {
        throw std::runtime_error("failed to write generator metadata");
    }
}
