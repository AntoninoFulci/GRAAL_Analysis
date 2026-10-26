#pragma once
#include <TLorentzVector.h>
#include <TTree.h>
#include <array>
#include <stdexcept>
#include <string>

// Fixed storage keeps ROOT branch addresses stable. Capturing truth consumes no
// random draws: the established smeared sample and its seeded stream stay intact.
struct GeneratorTruth {
    TLorentzVector beam, proton;
    std::array<TLorentzVector, 8> photons;

    GeneratorTruth(TTree &tree, int count) {
        if (count < 1 || count > static_cast<int>(photons.size()))
            throw std::invalid_argument("unsupported truth photon count");
        tree.Branch("beam_true", &beam);
        tree.Branch("proton_true", &proton);
        for (int i = 0; i < count; ++i)
            tree.Branch(("g" + std::to_string(i) + "_true").c_str(), &photons[i]);
    }
};
