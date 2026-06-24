#pragma once
#include <TLorentzVector.h>
#include <TRandom3.h>
#include <cmath>

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
