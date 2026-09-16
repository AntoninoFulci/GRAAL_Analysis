#pragma once
#include <TLorentzVector.h>
#include <TRandom3.h>
#include <TGenPhaseSpace.h>
#include <algorithm>
#include <cmath>
#include <stdexcept>

constexpr double kTaggerFwhmGeV = 0.016;
constexpr double kFwhmToSigma = 1.0 / 2.3548200450309493;
constexpr double kTaggerSigmaGeV = kTaggerFwhmGeV * kFwhmToSigma;

inline TLorentzVector SmearTaggedPhoton(double trueEnergy, TRandom3 &rng) {
    const double measuredEnergy = rng.Gaus(trueEnergy, kTaggerSigmaGeV);
    return TLorentzVector(0.0, 0.0, measuredEnergy, measuredEnergy);
}

inline bool AcceptPhaseSpaceWeight(double weight, TRandom3 &rng) {
    constexpr double tolerance = 1e-8;
    if (!std::isfinite(weight) || weight < -tolerance || weight > 1.0 + tolerance) {
        throw std::runtime_error(
            "TGenPhaseSpace returned a normalized weight outside [0, 1]"
        );
    }
    return rng.Uniform(0.0, 1.0) <= std::clamp(weight, 0.0, 1.0);
}

inline long long GenerateUnweighted(TGenPhaseSpace &phaseSpace, TRandom3 &rng) {
    long long attempts = 0;
    do {
        ++attempts;
    } while (!AcceptPhaseSpaceWeight(phaseSpace.Generate(), rng));
    return attempts;
}

inline TLorentzVector SmearPhoton(TLorentzVector p, TRandom3 &rng,
                                  double sE, double sTheta, double sPhi) {
    double E     = p.E();
    double theta = p.Theta();
    double phi   = p.Phi();
    double E_s     = rng.Gaus(E, sE * E);
    double theta_s = rng.Gaus(theta, sTheta);
    double phi_s   = rng.Gaus(phi, sPhi);
    double px = E_s * sin(theta_s) * cos(phi_s);
    double py = E_s * sin(theta_s) * sin(phi_s);
    double pz = E_s * cos(theta_s);
    return TLorentzVector(px, py, pz, E_s);
}

inline TLorentzVector SmearProton(TLorentzVector p, TRandom3 &rng,
                                  double relRes, double sTheta, double sPhi) {
    const double Mp = 0.938272;
    double P_s     = rng.Gaus(p.P(), relRes * p.P());
    double theta_s = rng.Gaus(p.Theta(), sTheta);
    double phi_s   = rng.Gaus(p.Phi(), sPhi);
    double px = P_s * sin(theta_s) * cos(phi_s);
    double py = P_s * sin(theta_s) * sin(phi_s);
    double pz = P_s * cos(theta_s);
    double E  = sqrt(P_s * P_s + Mp * Mp);
    return TLorentzVector(px, py, pz, E);
}
