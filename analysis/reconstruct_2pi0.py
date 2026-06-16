#!/usr/bin/env python3
# ============================================================
# Reconstruction of the gamma p -> p pi0 pi0 channel (two pi0).
#
# Reads the pre-analysis output (tree "h80", one entry per event
# with beam / protons / neutrons / gammas 4-vectors) produced by
# pre_analysis/PreAnalysis.C, pairs the four photons into the two
# pi0 candidates that best match the pi0 mass (chi2 minimisation
# over a table of index combinations), and writes a slimmer tree
# with the reconstructed 4-vectors.
#
# Run this BEFORE reconstruct_eta_pi0.py in the analysis workflow.
# ============================================================

import ROOT
import os
import numpy as np
from array import array


# ============================================================
# Configuration
# ============================================================

input_dir         = "subsample"             # folder with pre-analysis ROOT files
output_file       = "reco_2pi0.root"        # reconstruction output file
input_tree        = "h80"                   # pre-analysis tree name
output_tree       = "reco_2pi0"             # output tree name
combinations_file = "combinations_2pi0.txt" # photon-pairing table (i1 i2 i3 i4 m12 m34)

# ============================================================
# Load the photon-combination table
# Each row: gamma indices i1 i2 i3 i4 and the two target masses m12, m34
# ============================================================

combinations = np.loadtxt(combinations_file)

# ============================================================
# C++ include for 4D vectors
# ============================================================

ROOT.gInterpreter.Declare("""
#include <Math/Vector4D.h>
""")

# ============================================================
# Build the input TChain
# ============================================================

chain = ROOT.TChain(input_tree)

root_files = [
    f for f in os.listdir(input_dir)
    if f.endswith(".root") and f.startswith("analisi_")
]

print(f"Found {len(root_files)} ROOT files")

for f in root_files:
    fullpath = os.path.join(input_dir, f)
    chain.Add(fullpath)

n_entries = chain.GetEntries()
print("Total events in chain:", n_entries)

# ============================================================
# Output file + tree
# ============================================================

fout = ROOT.TFile(output_file, "RECREATE")
tout = ROOT.TTree(output_tree, output_tree)

# ============================================================
# Output branches
# ============================================================
chi2       = array('f', [0.])
pi0_1_mass = array('f', [0.])
pi0_2_mass = array('f', [0.])

beam         = ROOT.TLorentzVector()
target       = ROOT.TLorentzVector(0., 0., 0., 0.938272)  # proton at rest
proton       = ROOT.TLorentzVector()
neutron      = ROOT.TLorentzVector()
pi0_1        = ROOT.TLorentzVector()
pi0_1_gamma1 = ROOT.TLorentzVector()
pi0_1_gamma2 = ROOT.TLorentzVector()
pi0_2        = ROOT.TLorentzVector()
pi0_2_gamma1 = ROOT.TLorentzVector()
pi0_2_gamma2 = ROOT.TLorentzVector()
missing      = ROOT.TLorentzVector()  # missing 4-momentum: (beam+target) - (pi0_1+pi0_2)

tout.Branch("chi2", chi2, "chi2/F")
tout.Branch("pi0_1_mass", pi0_1_mass, "pi0_1_mass/F")
tout.Branch("pi0_2_mass", pi0_2_mass, "pi0_2_mass/F")

tout.Branch("beam", "TLorentzVector", beam)
tout.Branch("target", "TLorentzVector", target)
tout.Branch("proton", "TLorentzVector", proton)
tout.Branch("neutron", "TLorentzVector", neutron)
tout.Branch("pi0_1", "TLorentzVector", pi0_1)
tout.Branch("pi0_1_gamma1", "TLorentzVector", pi0_1_gamma1)
tout.Branch("pi0_1_gamma2", "TLorentzVector", pi0_1_gamma2)
tout.Branch("pi0_2", "TLorentzVector", pi0_2)
tout.Branch("pi0_2_gamma1", "TLorentzVector", pi0_2_gamma1)
tout.Branch("pi0_2_gamma2", "TLorentzVector", pi0_2_gamma2)
tout.Branch("missing", "TLorentzVector", missing)

# ============================================================
# Event loop
# ============================================================

print("Starting event loop...")

for iev in range(n_entries):
    chain.GetEntry(iev)

    if iev % 10000 == 0:
        print(f"Event {iev}/{n_entries}")

    # reset vectors
    beam.SetPxPyPzE(0, 0, chain.beam.E(), chain.beam.E())
    proton.SetPxPyPzE(0, 0, 0, 0)
    neutron.SetPxPyPzE(0, 0, 0, 0)
    pi0_1.SetPxPyPzE(0, 0, 0, 0)
    pi0_1_gamma1.SetPxPyPzE(0, 0, 0, 0)
    pi0_1_gamma2.SetPxPyPzE(0, 0, 0, 0)
    pi0_2.SetPxPyPzE(0, 0, 0, 0)
    pi0_2_gamma1.SetPxPyPzE(0, 0, 0, 0)
    pi0_2_gamma2.SetPxPyPzE(0, 0, 0, 0)
    missing.SetPxPyPzE(0, 0, 0, 0)

    if chain.neutrons.size() == 1:
        neutron.SetPxPyPzE(
            chain.neutrons[0].Px(),
            chain.neutrons[0].Py(),
            chain.neutrons[0].Pz(),
            chain.neutrons[0].E(),
        )
    if chain.protons.size() == 1:
        proton.SetPxPyPzE(
            chain.protons[0].Px(),
            chain.protons[0].Py(),
            chain.protons[0].Pz(),
            chain.protons[0].E(),
        )

    chi2_values = []

    # --------------------------------------------------------
    # chi2 for every photon-pairing combination
    # --------------------------------------------------------
    for i1, i2, i3, i4, m12, m34 in combinations:
        g12 = chain.gammas[int(i1)] + chain.gammas[int(i2)]
        g34 = chain.gammas[int(i3)] + chain.gammas[int(i4)]

        chi2_val = (
            ((g12.M() - m12) / (m12 * 0.08))**2 +
            ((g34.M() - m34) / (m34 * 0.08))**2
        )

        chi2_values.append(chi2_val)

    # best combination
    idx = chi2_values.index(min(chi2_values))
    chi2[0] = chi2_values[idx]
    if chi2[0] < 10:  # chi2 cut
        xx1 = chain.gammas[int(combinations[idx, 0])].Px()
        xx2 = chain.gammas[int(combinations[idx, 1])].Px()
        xx3 = chain.gammas[int(combinations[idx, 2])].Px()
        xx4 = chain.gammas[int(combinations[idx, 3])].Px()
        yy1 = chain.gammas[int(combinations[idx, 0])].Py()
        yy2 = chain.gammas[int(combinations[idx, 1])].Py()
        yy3 = chain.gammas[int(combinations[idx, 2])].Py()
        yy4 = chain.gammas[int(combinations[idx, 3])].Py()
        zz1 = chain.gammas[int(combinations[idx, 0])].Pz()
        zz2 = chain.gammas[int(combinations[idx, 1])].Pz()
        zz3 = chain.gammas[int(combinations[idx, 2])].Pz()
        zz4 = chain.gammas[int(combinations[idx, 3])].Pz()
        ee1 = chain.gammas[int(combinations[idx, 0])].E()
        ee2 = chain.gammas[int(combinations[idx, 1])].E()
        ee3 = chain.gammas[int(combinations[idx, 2])].E()
        ee4 = chain.gammas[int(combinations[idx, 3])].E()

        pi0_1.SetPxPyPzE(xx1 + xx2, yy1 + yy2, zz1 + zz2, ee1 + ee2)
        pi0_1_gamma1.SetPxPyPzE(xx1, yy1, zz1, ee1)
        pi0_1_gamma2.SetPxPyPzE(xx2, yy2, zz2, ee2)
        pi0_2.SetPxPyPzE(xx3 + xx4, yy3 + yy4, zz3 + zz4, ee3 + ee4)
        pi0_2_gamma1.SetPxPyPzE(xx3, yy3, zz3, ee3)
        pi0_2_gamma2.SetPxPyPzE(xx4, yy4, zz4, ee4)
        missing.SetPxPyPzE(
            ((beam + target) - (pi0_1 + pi0_2)).Px(),
            ((beam + target) - (pi0_1 + pi0_2)).Py(),
            ((beam + target) - (pi0_1 + pi0_2)).Pz(),
            ((beam + target) - (pi0_1 + pi0_2)).E()
        )
        pi0_1_mass[0] = pi0_1.M()
        pi0_2_mass[0] = pi0_2.M()

        tout.Fill()

fout.cd()
tout.Write()

n_written = tout.GetEntries()

fout.Close()

print("====================================")
print("Created file:", output_file)
print("Events written:", n_written)
print("===================================")
