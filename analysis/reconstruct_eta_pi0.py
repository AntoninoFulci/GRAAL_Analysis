#!/usr/bin/env python3
# ============================================================
# Reconstruction of the gamma p -> p eta pi0 channel.
#
# Reads the pre-analysis output (tree "h80", one entry per event
# with beam / protons / neutrons / gammas 4-vectors) produced by
# pre_analysis/PreAnalysis.C, pairs the four photons into an eta
# and a pi0 candidate (chi2 minimisation over a table of index
# combinations), and writes a slimmer tree with the reconstructed
# 4-vectors.
#
# For each best combination the pair whose target mass (column 5
# of the combination table) is above 0.4 GeV is assigned to the
# eta, the other to the pi0.
#
# Run this AFTER reconstruct_2pi0.py in the analysis workflow.
# ============================================================

import ROOT
import os
import numpy as np
from array import array
from pathlib import Path
from itertools import combinations as _combinations

# Stage-1 BDT gate (signal/background pre-filter)
_stage1_model = None
_stage1_threshold = None

def _load_stage1(model_dir: str = 'analysis/ml/model') -> bool:
    global _stage1_model, _stage1_threshold
    model_path = Path(model_dir) / 'bdt_stage1.json'
    thr_path   = Path(model_dir) / 'stage1_threshold.txt'
    if not model_path.exists():
        print(f'[stage1] model not found at {model_path}, gate disabled')
        return False
    try:
        import xgboost as xgb
        _stage1_model = xgb.XGBClassifier()
        _stage1_model.load_model(str(model_path))
        _stage1_threshold = float(thr_path.read_text().strip())
        print(f'[stage1] loaded model, threshold={_stage1_threshold:.4f}')
        return True
    except Exception as e:
        print(f'[stage1] load failed ({e}), gate disabled')
        return False

def _stage1_pass(gammas_px, gammas_py, gammas_pz, gammas_E,
                 proton_px, proton_py, proton_pz, proton_E,
                 beam_E) -> bool:
    """Return True if event passes stage-1 BDT."""
    if _stage1_model is None:
        return True
    import numpy as np
    M = len(gammas_E)
    feat = np.zeros(24, dtype=np.float32)
    # pair invariant masses (up to 15 pairs of 6 photons)
    _MPI0 = 0.134977; _META = 0.547862
    pair_masses = []
    for i, j in _combinations(range(min(M, 6)), 2):
        dx = gammas_px[i]+gammas_px[j]; dy = gammas_py[i]+gammas_py[j]
        dz = gammas_pz[i]+gammas_pz[j]; de = gammas_E[i]+gammas_E[j]
        m2 = de**2 - dx**2 - dy**2 - dz**2
        pair_masses.append(float(np.sqrt(max(m2, 0.0))))
    for k, m in enumerate(pair_masses[:15]):
        feat[k] = m
    feat[15] = sum(1 for m in pair_masses if abs(m - _MPI0) < 0.040)
    feat[16] = sum(1 for m in pair_masses if abs(m - _META) < 0.080)
    # best chi2 with first 4 photons
    best_chi2 = 999.0
    gs = list(zip(gammas_px, gammas_py, gammas_pz, gammas_E))
    for (i,j) in _combinations(range(min(M,4)), 2):
        rem = [k for k in range(min(M,4)) if k not in (i,j)]
        for (k,l) in _combinations(rem, 2):
            for mtgt1, mtgt2 in [(_META, _MPI0), (_MPI0, _META)]:
                p1 = [gs[i][c]+gs[j][c] for c in range(4)]
                p2 = [gs[k][c]+gs[l][c] for c in range(4)]
                m1 = float(np.sqrt(max(p1[3]**2-p1[0]**2-p1[1]**2-p1[2]**2,0)))
                m2v = float(np.sqrt(max(p2[3]**2-p2[0]**2-p2[1]**2-p2[2]**2,0)))
                c = ((m1-mtgt1)/(0.08*mtgt1))**2 + ((m2v-mtgt2)/(0.08*mtgt2))**2
                if c < best_chi2: best_chi2 = c
    feat[17] = best_chi2
    # missing mass
    Mp = 0.938272
    tot_E = beam_E + Mp; tot_pz = beam_E
    miss_E = tot_E - proton_E; miss_pz = tot_pz - proton_pz
    miss_px = -proton_px; miss_py = -proton_py
    miss_m2 = miss_E**2 - miss_px**2 - miss_py**2 - miss_pz**2
    feat[18] = float(np.sqrt(max(miss_m2, 0.0)))
    feat[19] = miss_E
    feat[20] = float(sum(gammas_E))
    feat[21] = float(M)
    p_mom = float(np.sqrt(proton_px**2 + proton_py**2 + proton_pz**2))
    feat[22] = p_mom
    feat[23] = proton_pz / p_mom if p_mom > 0 else 0.0
    score = _stage1_model.predict_proba(feat.reshape(1, -1))[0, 1]
    return float(score) >= _stage1_threshold


# ============================================================
# Configuration
# ============================================================

input_dir         = "subsample"                # folder with pre-analysis ROOT files
output_file       = "reco_eta_pi0.root"        # reconstruction output file
input_tree        = "h80"                      # pre-analysis tree name
output_tree       = "reco_eta_pi0"             # output tree name
combinations_file = "combinations_eta_pi0.txt" # photon-pairing table (i1 i2 i3 i4 m12 m34)

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
chi2     = array('f', [0.])
eta_mass = array('f', [0.])
pi0_mass = array('f', [0.])

beam       = ROOT.TLorentzVector()
target     = ROOT.TLorentzVector(0., 0., 0., 0.938272)  # proton at rest
proton     = ROOT.TLorentzVector()
neutron    = ROOT.TLorentzVector()
eta        = ROOT.TLorentzVector()
eta_gamma1 = ROOT.TLorentzVector()
eta_gamma2 = ROOT.TLorentzVector()
pi0        = ROOT.TLorentzVector()
pi0_gamma1 = ROOT.TLorentzVector()
pi0_gamma2 = ROOT.TLorentzVector()
missing    = ROOT.TLorentzVector()  # missing 4-momentum: (beam+target) - (eta+pi0)

tout.Branch("chi2", chi2, "chi2/F")
tout.Branch("eta_mass", eta_mass, "eta_mass/F")
tout.Branch("pi0_mass", pi0_mass, "pi0_mass/F")

tout.Branch("beam", "TLorentzVector", beam)
tout.Branch("target", "TLorentzVector", target)
tout.Branch("proton", "TLorentzVector", proton)
tout.Branch("neutron", "TLorentzVector", neutron)
tout.Branch("eta", "TLorentzVector", eta)
tout.Branch("eta_gamma1", "TLorentzVector", eta_gamma1)
tout.Branch("eta_gamma2", "TLorentzVector", eta_gamma2)
tout.Branch("pi0", "TLorentzVector", pi0)
tout.Branch("pi0_gamma1", "TLorentzVector", pi0_gamma1)
tout.Branch("pi0_gamma2", "TLorentzVector", pi0_gamma2)
tout.Branch("missing", "TLorentzVector", missing)

# ============================================================
# Event loop
# ============================================================

_load_stage1()
print("Starting event loop...")

for iev in range(n_entries):
    chain.GetEntry(iev)

    if iev % 10000 == 0:
        print(f"Event {iev}/{n_entries}")

    # stage-1 BDT gate: reject background-like events early
    if chain.gammas.size() >= 4:
        gex = [chain.gammas[k].Px() for k in range(chain.gammas.size())]
        gey = [chain.gammas[k].Py() for k in range(chain.gammas.size())]
        gez = [chain.gammas[k].Pz() for k in range(chain.gammas.size())]
        geE = [chain.gammas[k].E()  for k in range(chain.gammas.size())]
        if not _stage1_pass(gex, gey, gez, geE,
                            chain.protons[0].Px() if chain.protons.size() else 0,
                            chain.protons[0].Py() if chain.protons.size() else 0,
                            chain.protons[0].Pz() if chain.protons.size() else 0,
                            chain.protons[0].E()  if chain.protons.size() else 0,
                            chain.beam.E()):
            continue

    # reset vectors
    beam.SetPxPyPzE(0, 0, chain.beam.E(), chain.beam.E())
    proton.SetPxPyPzE(0, 0, 0, 0)
    neutron.SetPxPyPzE(0, 0, 0, 0)
    eta.SetPxPyPzE(0, 0, 0, 0)
    eta_gamma1.SetPxPyPzE(0, 0, 0, 0)
    eta_gamma2.SetPxPyPzE(0, 0, 0, 0)
    pi0.SetPxPyPzE(0, 0, 0, 0)
    pi0_gamma1.SetPxPyPzE(0, 0, 0, 0)
    pi0_gamma2.SetPxPyPzE(0, 0, 0, 0)
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

        # the pair with target mass > 0.4 GeV is the eta, the other the pi0
        if combinations[idx, 4] > 0.4:
            eta.SetPxPyPzE(xx1 + xx2, yy1 + yy2, zz1 + zz2, ee1 + ee2)
            eta_gamma1.SetPxPyPzE(xx1, yy1, zz1, ee1)
            eta_gamma2.SetPxPyPzE(xx2, yy2, zz2, ee2)
            pi0.SetPxPyPzE(xx3 + xx4, yy3 + yy4, zz3 + zz4, ee3 + ee4)
            pi0_gamma1.SetPxPyPzE(xx3, yy3, zz3, ee3)
            pi0_gamma2.SetPxPyPzE(xx4, yy4, zz4, ee4)
        else:
            pi0.SetPxPyPzE(xx1 + xx2, yy1 + yy2, zz1 + zz2, ee1 + ee2)
            pi0_gamma1.SetPxPyPzE(xx1, yy1, zz1, ee1)
            pi0_gamma2.SetPxPyPzE(xx2, yy2, zz2, ee2)
            eta.SetPxPyPzE(xx3 + xx4, yy3 + yy4, zz3 + zz4, ee3 + ee4)
            eta_gamma1.SetPxPyPzE(xx3, yy3, zz3, ee3)
            eta_gamma2.SetPxPyPzE(xx4, yy4, zz4, ee4)
        missing.SetPxPyPzE(
            ((beam + target) - (eta + pi0)).Px(),
            ((beam + target) - (eta + pi0)).Py(),
            ((beam + target) - (eta + pi0)).Pz(),
            ((beam + target) - (eta + pi0)).E()
        )
        eta_mass[0] = eta.M()
        pi0_mass[0] = pi0.M()

        tout.Fill()

fout.cd()
tout.Write("", ROOT.TObject.kOverwrite)  # reuse the key, avoid extra ;N cycles

n_written = tout.GetEntries()

fout.Close()

print("====================================")
print("Created file:", output_file)
print("Events written:", n_written)
print("===================================")
