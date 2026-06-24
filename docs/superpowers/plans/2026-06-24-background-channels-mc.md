# Background Channels MC + Two-Stage BDT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five background MC generators, a photon-loss model, and a stage-1 signal/background BDT so the existing pairing BDT (stage 2) only runs on events already identified as signal-like.

**Architecture:** Separate ROOT macros generate each background channel writing all true photons; a Python photon-loss model then filters to exactly 4γ events; `build_background_features.py` merges signal + background into a 24-dim feature matrix for the stage-1 BDT; `reconstruct_eta_pi0.py` gates events through stage-1 before calling stage-2.

**Tech Stack:** ROOT/TGenPhaseSpace (C++), Python 3, uproot 5, numpy ≥2.0, xgboost 3.2, scikit-learn 1.9, pytest ≥8.0, matplotlib ≥3.10.

## Global Constraints

- All ROOT macros use `TObject::kOverwrite` when writing TTrees.
- 4-vectors everywhere: `[E, px, py, pz]` (last axis).
- Background branch naming: `g0`..`gN`, `proton`, `beam`, `n_true_gamma`.
- Signal generator (`generate_eta_pi0_dataset.C`) is **not modified**.
- `LossParams` default: E_thr=0.050 GeV, sigma_E=0.020 GeV, theta_acc=0.436 rad, sigma_theta=0.087 rad.
- Stage-1 threshold stored in `analysis/ml/model/stage1_threshold.txt` (single float).
- `cross_sections.csv` is single source of truth for sample weights.
- All new Python modules live under `analysis/ml/`.
- Tests live in `analysis/ml/tests/`.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `simulation/smearing.h` | Create | Shared `SmearPhoton` / `SmearProton` for background generators |
| `simulation/generate_pi0pi0_dataset.C` | Create | γp→pπ0π0 (4γ) |
| `simulation/generate_3pi0_dataset.C` | Create | γp→p3π0 (6γ) |
| `simulation/generate_eta_2pi0_dataset.C` | Create | γp→pηπ0π0 (6γ) |
| `simulation/generate_omega_pi0_dataset.C` | Create | γp→pωπ0, ω→γπ0 (5γ) |
| `simulation/generate_etaprime_dataset.C` | Create | γp→pη', η'→ηπ0π0 (6γ) |
| `simulation/cross_sections.csv` | Create | σ_ref and P_survival per channel |
| `analysis/ml/photon_loss.py` | Create | `LossParams`, `p_loss`, `apply_loss_events`, `--estimate-survival` CLI |
| `analysis/ml/build_background_features.py` | Create | Load, loss, 24-dim features, labels, weights → `features_stage1.npz` |
| `analysis/ml/train_bdt_stage1.py` | Create | Binary XGBoost, ROC/score/importance plots, threshold file |
| `analysis/reconstruct_eta_pi0.py` | Modify | Load stage-1 model at startup, gate each event |
| `analysis/ml/tests/test_photon_loss.py` | Create | Unit tests for `photon_loss.py` |
| `analysis/ml/tests/test_build_background_features.py` | Create | Unit tests for feature builder |

---

## Task 1: Shared Smearing Header

**Files:**
- Create: `simulation/smearing.h`

**Interfaces:**
- Produces: `SmearPhoton(TLorentzVector, TRandom3&, double sE, double sTheta, double sPhi) → TLorentzVector`
- Produces: `SmearProton(TLorentzVector, TRandom3&, double relRes, double sTheta, double sPhi) → TLorentzVector`

- [ ] **Step 1: Create `simulation/smearing.h`**

```cpp
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
```

- [ ] **Step 2: Verify header compiles inside ROOT**

```bash
root -l -e '#include "simulation/smearing.h"; printf("OK\n"); gApplication->Terminate(0);'
```
Expected: prints `OK` with no error.

- [ ] **Step 3: Commit**

```bash
git add simulation/smearing.h
git commit -m "feat: add shared smearing header for background MC generators"
```

---

## Task 2: π0π0 Generator (4γ)

**Files:**
- Create: `simulation/generate_pi0pi0_dataset.C`

**Interfaces:**
- Produces: `simulation/pi0pi0_mc.root` tree `mc` with branches `g0..g3`, `proton`, `beam`, `n_true_gamma=4`

- [ ] **Step 1: Create generator**

```cpp
#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_pi0pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double mpi0 = 0.134977;
    const double threshold = (pow(2*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("pi0pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "pi0pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3;
    int n_true_gamma = 4;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0", &g0); tree->Branch("g1", &g1);
    tree->Branch("g2", &g2); tree->Branch("g3", &g3);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam, 0.016), rng.Gaus(Ebeam, 0.016));
        TLorentzVector target(0, 0, 0, mp);
        TLorentzVector W = TLorentzVector(0,0,Ebeam,Ebeam) + target;

        double masses3[3] = {mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 3, masses3)) continue;
        evt.Generate();

        TLorentzVector pi0a = *evt.GetDecay(0);
        TLorentzVector pi0b = *evt.GetDecay(1);
        proton = *evt.GetDecay(2);

        double m2[2] = {0., 0.};
        TGenPhaseSpace da, db;
        da.SetDecay(pi0a, 2, m2); da.Generate();
        db.SetDecay(pi0b, 2, m2); db.Generate();

        g0 = SmearPhoton(*da.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*da.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*db.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*db.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d pi0pi0 events\n", Nevents);
}
```

- [ ] **Step 2: Generate test sample and verify**

```bash
cd simulation && root -l 'generate_pi0pi0_dataset.C(10000)' && cd ..
root -l -e 'auto f=TFile::Open("simulation/pi0pi0_mc.root"); auto t=(TTree*)f->Get("mc"); t->Print(); gApplication->Terminate(0);'
```
Expected: branches `g0..g3`, `proton`, `beam`, `n_true_gamma`, 10000 entries.

- [ ] **Step 3: Commit**

```bash
git add simulation/generate_pi0pi0_dataset.C
git commit -m "feat: add pi0pi0 background MC generator"
```

---

## Task 3: 3π0 Generator (6γ)

**Files:**
- Create: `simulation/generate_3pi0_dataset.C`

**Interfaces:**
- Produces: `simulation/3pi0_mc.root` tree `mc` with branches `g0..g5`, `proton`, `beam`, `n_true_gamma=6`

- [ ] **Step 1: Create generator**

```cpp
#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_3pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double mpi0 = 0.134977;
    const double threshold = (pow(3*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("3pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "3pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5;
    int n_true_gamma = 6;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam,0.016), rng.Gaus(Ebeam,0.016));
        TLorentzVector target(0,0,0,mp);
        TLorentzVector W = TLorentzVector(0,0,Ebeam,Ebeam) + target;

        double masses4[4] = {mpi0, mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 4, masses4)) continue;
        evt.Generate();

        TLorentzVector pi[3];
        pi[0]=*evt.GetDecay(0); pi[1]=*evt.GetDecay(1); pi[2]=*evt.GetDecay(2);
        proton = *evt.GetDecay(3);

        double m2[2] = {0.,0.};
        TLorentzVector tmp[6];
        TGenPhaseSpace d[3];
        for (int k=0; k<3; k++) {
            d[k].SetDecay(pi[k], 2, m2); d[k].Generate();
            tmp[2*k]   = SmearPhoton(*d[k].GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
            tmp[2*k+1] = SmearPhoton(*d[k].GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        }
        g0=tmp[0]; g1=tmp[1]; g2=tmp[2]; g3=tmp[3]; g4=tmp[4]; g5=tmp[5];
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d 3pi0 events\n", Nevents);
}
```

- [ ] **Step 2: Generate and verify**

```bash
cd simulation && root -l 'generate_3pi0_dataset.C(10000)' && cd ..
root -l -e 'auto f=TFile::Open("simulation/3pi0_mc.root"); auto t=(TTree*)f->Get("mc"); printf("entries=%lld\n",t->GetEntries()); gApplication->Terminate(0);'
```
Expected: entries=10000.

- [ ] **Step 3: Commit**

```bash
git add simulation/generate_3pi0_dataset.C
git commit -m "feat: add 3pi0 background MC generator"
```

---

## Task 4: η π0π0 Generator (6γ)

**Files:**
- Create: `simulation/generate_eta_2pi0_dataset.C`

**Interfaces:**
- Produces: `simulation/eta_2pi0_mc.root` tree `mc` with branches `g0..g5`, `proton`, `beam`, `n_true_gamma=6`

- [ ] **Step 1: Create generator**

```cpp
#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_eta_2pi0_dataset(int Nevents = 1000000) {
    const double mp   = 0.938272;
    const double meta = 0.547862;
    const double mpi0 = 0.134977;
    const double threshold = (pow(meta + 2*mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("eta_2pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "eta 2pi0 background MC");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5;
    int n_true_gamma = 6;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam,0.016), rng.Gaus(Ebeam,0.016));
        TLorentzVector target(0,0,0,mp);
        TLorentzVector W = TLorentzVector(0,0,Ebeam,Ebeam) + target;

        double masses4[4] = {meta, mpi0, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 4, masses4)) continue;
        evt.Generate();

        TLorentzVector eta_v = *evt.GetDecay(0);
        TLorentzVector pi0a  = *evt.GetDecay(1);
        TLorentzVector pi0b  = *evt.GetDecay(2);
        proton = *evt.GetDecay(3);

        double m2[2] = {0.,0.};
        TGenPhaseSpace de, da, db;
        de.SetDecay(eta_v, 2, m2); de.Generate();
        da.SetDecay(pi0a,  2, m2); da.Generate();
        db.SetDecay(pi0b,  2, m2); db.Generate();

        g0 = SmearPhoton(*de.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*de.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*da.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*da.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g4 = SmearPhoton(*db.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g5 = SmearPhoton(*db.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d eta+2pi0 events\n", Nevents);
}
```

- [ ] **Step 2: Generate and verify**

```bash
cd simulation && root -l 'generate_eta_2pi0_dataset.C(10000)' && cd ..
root -l -e 'auto f=TFile::Open("simulation/eta_2pi0_mc.root"); auto t=(TTree*)f->Get("mc"); printf("entries=%lld\n",t->GetEntries()); gApplication->Terminate(0);'
```
Expected: entries close to 10000 (threshold 1.174 GeV, narrow range, some rejection).

- [ ] **Step 3: Commit**

```bash
git add simulation/generate_eta_2pi0_dataset.C
git commit -m "feat: add eta+2pi0 background MC generator"
```

---

## Task 5: ω π0 Generator (5γ)

**Files:**
- Create: `simulation/generate_omega_pi0_dataset.C`

**Interfaces:**
- Produces: `simulation/omega_pi0_mc.root` tree `mc` with branches `g0..g4`, `proton`, `beam`, `n_true_gamma=5`
- g0 = direct γ from ω→γπ0; g1,g2 from ω's π0 decay; g3,g4 from outer π0 decay

- [ ] **Step 1: Create generator**

```cpp
#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_omega_pi0_dataset(int Nevents = 1000000) {
    const double mp     = 0.938272;
    const double momega = 0.78265;
    const double mpi0   = 0.134977;
    const double threshold = (pow(momega + mpi0 + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("omega_pi0_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "omega pi0 background MC (omega->gamma pi0)");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4;
    int n_true_gamma = 5;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam,0.016), rng.Gaus(Ebeam,0.016));
        TLorentzVector target(0,0,0,mp);
        TLorentzVector W = TLorentzVector(0,0,Ebeam,Ebeam) + target;

        double masses3[3] = {momega, mpi0, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 3, masses3)) continue;
        evt.Generate();

        TLorentzVector omega_v   = *evt.GetDecay(0);
        TLorentzVector outer_pi0 = *evt.GetDecay(1);
        proton = *evt.GetDecay(2);

        // omega -> gamma + pi0
        double m_omega_decay[2] = {0., mpi0};
        TGenPhaseSpace domega;
        domega.SetDecay(omega_v, 2, m_omega_decay);
        domega.Generate();

        TLorentzVector omega_gamma = *domega.GetDecay(0);
        TLorentzVector omega_pi0  = *domega.GetDecay(1);

        double m2[2] = {0.,0.};
        TGenPhaseSpace dopi, dout;
        dopi.SetDecay(omega_pi0,  2, m2); dopi.Generate();
        dout.SetDecay(outer_pi0,  2, m2); dout.Generate();

        g0 = SmearPhoton(omega_gamma,       rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*dopi.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*dopi.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*dout.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g4 = SmearPhoton(*dout.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d omega+pi0 events\n", Nevents);
}
```

- [ ] **Step 2: Generate and verify**

```bash
cd simulation && root -l 'generate_omega_pi0_dataset.C(10000)' && cd ..
root -l -e 'auto f=TFile::Open("simulation/omega_pi0_mc.root"); auto t=(TTree*)f->Get("mc"); printf("entries=%lld\n",t->GetEntries()); gApplication->Terminate(0);'
```

- [ ] **Step 3: Commit**

```bash
git add simulation/generate_omega_pi0_dataset.C
git commit -m "feat: add omega+pi0 background MC generator (omega->gamma pi0)"
```

---

## Task 6: η' Generator (6γ)

**Files:**
- Create: `simulation/generate_etaprime_dataset.C`

**Interfaces:**
- Produces: `simulation/etaprime_mc.root` tree `mc` with branches `g0..g5`, `proton`, `beam`, `n_true_gamma=6`
- Decay chain: η'→ηπ0π0 → g0,g1 from η; g2,g3 from π0a; g4,g5 from π0b

- [ ] **Step 1: Create generator**

```cpp
#include <TFile.h>
#include <TTree.h>
#include <TRandom3.h>
#include <TLorentzVector.h>
#include <TGenPhaseSpace.h>
#include <TMath.h>
#include "smearing.h"

void generate_etaprime_dataset(int Nevents = 1000000) {
    const double mp    = 0.938272;
    const double metap = 0.95778;
    const double meta  = 0.547862;
    const double mpi0  = 0.134977;
    const double threshold = (pow(metap + mp, 2) - pow(mp, 2)) / (2*mp);

    TRandom3 rng(0);
    TFile *fout = new TFile("etaprime_mc.root", "RECREATE");
    TTree *tree = new TTree("mc", "eta-prime background MC (eta'->eta pi0 pi0)");

    TLorentzVector beam, proton, g0, g1, g2, g3, g4, g5;
    int n_true_gamma = 6;

    tree->Branch("beam",   &beam);
    tree->Branch("proton", &proton);
    tree->Branch("g0",&g0); tree->Branch("g1",&g1); tree->Branch("g2",&g2);
    tree->Branch("g3",&g3); tree->Branch("g4",&g4); tree->Branch("g5",&g5);
    tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");

    for (int i = 0; i < Nevents; i++) {
        double Ebeam = rng.Uniform(threshold, 1.55);
        beam.SetPxPyPzE(0, 0, rng.Gaus(Ebeam,0.016), rng.Gaus(Ebeam,0.016));
        TLorentzVector target(0,0,0,mp);
        TLorentzVector W = TLorentzVector(0,0,Ebeam,Ebeam) + target;

        double masses2[2] = {metap, mp};
        TGenPhaseSpace evt;
        if (!evt.SetDecay(W, 2, masses2)) continue;
        evt.Generate();

        TLorentzVector etap_v = *evt.GetDecay(0);
        proton = *evt.GetDecay(1);

        double masses_decay[3] = {meta, mpi0, mpi0};
        TGenPhaseSpace detap;
        if (!detap.SetDecay(etap_v, 3, masses_decay)) continue;
        detap.Generate();

        TLorentzVector eta_v = *detap.GetDecay(0);
        TLorentzVector pi0a  = *detap.GetDecay(1);
        TLorentzVector pi0b  = *detap.GetDecay(2);

        double m2[2] = {0.,0.};
        TGenPhaseSpace de, da, db;
        de.SetDecay(eta_v, 2, m2); de.Generate();
        da.SetDecay(pi0a,  2, m2); da.Generate();
        db.SetDecay(pi0b,  2, m2); db.Generate();

        g0 = SmearPhoton(*de.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g1 = SmearPhoton(*de.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g2 = SmearPhoton(*da.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g3 = SmearPhoton(*da.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g4 = SmearPhoton(*db.GetDecay(0), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        g5 = SmearPhoton(*db.GetDecay(1), rng, 0.10, 5*TMath::DegToRad(), 3*TMath::DegToRad());
        proton = SmearProton(proton, rng, 0.04, 3*TMath::DegToRad(), 2*TMath::DegToRad());

        tree->Fill();
    }
    tree->Write("", TObject::kOverwrite);
    fout->Close();
    printf("Generated %d eta-prime events\n", Nevents);
}
```

- [ ] **Step 2: Generate and verify**

```bash
cd simulation && root -l 'generate_etaprime_dataset.C(10000)' && cd ..
root -l -e 'auto f=TFile::Open("simulation/etaprime_mc.root"); auto t=(TTree*)f->Get("mc"); printf("entries=%lld\n",t->GetEntries()); gApplication->Terminate(0);'
```
Note: threshold 1.4465 GeV, max 1.55 GeV — narrow range, expect ~2000–4000 entries from 10000 attempts.

- [ ] **Step 3: Commit**

```bash
git add simulation/generate_etaprime_dataset.C
git commit -m "feat: add eta-prime background MC generator (eta'->eta pi0 pi0)"
```

---

## Task 7: Cross-Sections CSV

**Files:**
- Create: `simulation/cross_sections.csv`

**Interfaces:**
- Consumed by: `build_background_features.py` — `_load_cross_sections()` reads columns `channel`, `sigma_ref_ub`, `p_survival`, `sigma_eff`

- [ ] **Step 1: Create `simulation/cross_sections.csv`**

```
# Cross-section weights for stage-1 BDT training.
# sigma_ref_ub: reference cross section in microbarn at Ebeam ~ 1.3 GeV.
# p_survival: fraction of generated events surviving 4-gamma filter (default LossParams).
# sigma_eff = sigma_ref_ub * p_survival
# LossParams used for p_survival: E_thr=0.050 sigma_E=0.020 theta_acc=0.436 theta_sigma=0.087
# References: CB-ELSA/TAPS (Sarantsev, Thoma, Kashevarov); SAPHIR (Barth); CB-ELSA (Crede); PDG BRs.
channel,sigma_ref_ub,p_survival,sigma_eff
eta_pi0,1.5,1.00,1.50
pi0pi0,12.0,1.00,12.00
3pi0,6.0,0.08,0.48
eta_2pi0,0.5,0.08,0.04
omega_pi0,0.6,0.15,0.09
etaprime,0.2,0.05,0.01
```

- [ ] **Step 2: Verify CSV parses**

```bash
python3 -c "
import csv
with open('simulation/cross_sections.csv') as f:
    rows = list(csv.DictReader(r for r in f if not r.startswith('#')))
for r in rows:
    print(r['channel'], float(r['sigma_eff']))
assert len(rows) == 6
print('OK')
"
```
Expected: 6 lines then `OK`.

- [ ] **Step 3: Commit**

```bash
git add simulation/cross_sections.csv
git commit -m "feat: add cross-sections CSV for stage-1 BDT sample weights"
```

---

## Task 8: Photon Loss Model

**Files:**
- Create: `analysis/ml/photon_loss.py`
- Create: `analysis/ml/tests/test_photon_loss.py`

**Interfaces:**
- Produces:
  - `LossParams` dataclass: `E_thr=0.050`, `sigma_E=0.020`, `theta_acc=0.436`, `sigma_theta=0.087`
  - `p_loss(E: ndarray, theta: ndarray, params: LossParams) → ndarray` (same shape as inputs)
  - `apply_loss_events(photons: ndarray (N,n_gamma,4), params: LossParams, rng: np.random.Generator) → tuple[ndarray (M,4,4), ndarray (M,)]`
  - CLI `--estimate-survival --n-gamma INT` prints P_survival to stdout

- [ ] **Step 1: Write failing tests in `analysis/ml/tests/test_photon_loss.py`**

```python
import numpy as np
import pytest
from analysis.ml.photon_loss import LossParams, p_loss, apply_loss_events

DEFAULT = LossParams()


def test_p_loss_high_energy_barrel_near_zero():
    E = np.array([1.0])
    theta = np.array([np.pi / 2])
    assert p_loss(E, theta, DEFAULT) < 0.02


def test_p_loss_low_energy_large():
    E = np.array([0.010])
    theta = np.array([np.pi / 2])
    assert p_loss(E, theta, DEFAULT) > 0.80


def test_p_loss_very_forward_large():
    E = np.array([1.0])
    theta = np.array([2.0 * np.pi / 180])
    assert p_loss(E, theta, DEFAULT) > 0.50


def test_p_loss_broadcast_shape():
    E = np.ones((100, 6))
    theta = np.full((100, 6), np.pi / 2)
    assert p_loss(E, theta, DEFAULT).shape == (100, 6)


def test_apply_loss_events_returns_exactly_4_photons():
    rng = np.random.default_rng(1)
    N = 500
    photons = np.zeros((N, 6, 4))
    photons[:, :, 0] = np.linspace(0.02, 0.8, 6)
    photons[:, :, 1] = photons[:, :, 0]
    survived, indices = apply_loss_events(photons, DEFAULT, rng)
    assert survived.shape[1] == 4
    assert survived.shape[2] == 4


def test_apply_loss_events_indices_valid():
    rng = np.random.default_rng(2)
    N = 200
    photons = np.zeros((N, 5, 4))
    photons[:, :, 0] = 0.3
    photons[:, :, 1] = 0.3
    _, indices = apply_loss_events(photons, DEFAULT, rng)
    assert np.all(indices >= 0) and np.all(indices < N)


def test_apply_loss_events_4gamma_high_eff():
    rng = np.random.default_rng(0)
    N = 1000
    photons = np.zeros((N, 4, 4))
    photons[:, :, 0] = 0.5
    photons[:, :, 1] = 0.5   # px=E, pz=0 -> theta~90 deg barrel
    survived, _ = apply_loss_events(photons, DEFAULT, rng)
    assert len(survived) > 800
```

- [ ] **Step 2: Confirm tests fail**

```bash
python -m pytest analysis/ml/tests/test_photon_loss.py -v 2>&1 | head -5
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `analysis/ml/photon_loss.py`**

```python
"""Photon detection loss model for GRAAL background MC processing."""
from __future__ import annotations
import argparse
from dataclasses import dataclass

import numpy as np


@dataclass
class LossParams:
    E_thr: float = 0.050
    sigma_E: float = 0.020
    theta_acc: float = 0.436   # rad (25 deg)
    sigma_theta: float = 0.087 # rad (5 deg)


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))


def p_loss(E: np.ndarray, theta: np.ndarray, params: LossParams) -> np.ndarray:
    """Element-wise probability of losing a photon with energy E (GeV) at angle theta (rad)."""
    p_thr = _sigmoid(-(E - params.E_thr) / params.sigma_E)
    p_acc = _sigmoid((np.abs(theta - np.pi / 2) - params.theta_acc) / params.sigma_theta)
    return 1.0 - (1.0 - p_thr) * (1.0 - p_acc)


def _theta_from_4vec(photons: np.ndarray) -> np.ndarray:
    pz = photons[..., 3]
    p_mag = np.sqrt(photons[..., 1]**2 + photons[..., 2]**2 + pz**2)
    return np.arccos(np.clip(pz / np.where(p_mag > 0, p_mag, 1.0), -1.0, 1.0))


def apply_loss_events(
    photons: np.ndarray,
    params: LossParams,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply loss per photon; return events where exactly 4 photons survive.

    photons: (N, n_gamma, 4) — [E, px, py, pz]
    Returns: (survived (M,4,4), original_indices (M,))
    """
    N, n_gamma = photons.shape[:2]
    E = photons[:, :, 0]
    theta = _theta_from_4vec(photons)

    alive = rng.random((N, n_gamma)) >= p_loss(E, theta, params)
    mask = alive.sum(axis=1) == 4
    orig = np.where(mask)[0]

    result = np.empty((len(orig), 4, 4), dtype=np.float64)
    for j, i in enumerate(orig):
        result[j] = photons[i, alive[i], :]
    return result, orig


def estimate_survival(n_gamma: int, params: LossParams, n_samples: int = 500_000) -> float:
    """Monte-Carlo estimate of P(exactly 4 survive) for flat E and theta distributions."""
    rng = np.random.default_rng(0)
    E = rng.uniform(0.05, 0.6, (n_samples, n_gamma))
    theta = rng.uniform(0, np.pi, (n_samples, n_gamma))
    alive = (rng.random((n_samples, n_gamma)) >= p_loss(E, theta, params)).sum(axis=1)
    return float((alive == 4).mean())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--estimate-survival", action="store_true")
    ap.add_argument("--n-gamma", type=int, default=6)
    ap.add_argument("--n-samples", type=int, default=500_000)
    args = ap.parse_args()
    if args.estimate_survival:
        params = LossParams()
        p = estimate_survival(args.n_gamma, params, args.n_samples)
        print(f"P_survival(n_gamma={args.n_gamma}) = {p:.4f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Confirm tests pass**

```bash
python -m pytest analysis/ml/tests/test_photon_loss.py -v
```
Expected: all 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/photon_loss.py analysis/ml/tests/test_photon_loss.py
git commit -m "feat: add photon loss model (LossParams, p_loss, apply_loss_events)"
```

---

## Task 9: Background Feature Builder

**Files:**
- Create: `analysis/ml/build_background_features.py`
- Create: `analysis/ml/tests/test_build_background_features.py`

**Interfaces:**
- Consumes: `apply_loss_events`, `load_signal_photons` (alias of `build_features.load_photons`), `load_beam`, `physics.*`, `cross_sections.csv`
- Produces:
  - `load_bg_photons(path, n_gamma, tree="mc", n_max=None) → ndarray (N,n_gamma,4)`
  - `load_proton_beam(path, tree="mc", n_max=None) → tuple[ndarray (N,4), ndarray (N,4)]`
  - `compute_stage1_features(photons (N,4,4), proton (N,4), beam (N,4)) → ndarray (N,24)`
  - `FEATURE_NAMES_S1: list[str]` — 24 names in column order
  - `analysis/ml/data/features_stage1.npz` with keys `X (N,24)`, `y (N,)`, `w (N,)`, `feature_names`

- [ ] **Step 1: Write failing tests in `analysis/ml/tests/test_build_background_features.py`**

```python
import numpy as np
import pytest
from analysis.ml.build_background_features import compute_stage1_features, FEATURE_NAMES_S1

MP = 0.938272


def _photons(N=50, seed=0):
    rng = np.random.default_rng(seed)
    ph = np.zeros((N, 4, 4))
    ph[:, :, 0] = rng.uniform(0.1, 0.4, (N, 4))
    ph[:, :, 1] = rng.uniform(-0.1, 0.1, (N, 4))
    ph[:, :, 2] = rng.uniform(-0.1, 0.1, (N, 4))
    ph[:, :, 3] = rng.uniform(0.05, 0.35, (N, 4))
    return ph


def _proton(N=50):
    rng = np.random.default_rng(1)
    p = np.zeros((N, 4))
    p[:, 0] = rng.uniform(MP, MP + 0.3, N)
    p[:, 3] = np.sqrt(np.clip(p[:, 0]**2 - MP**2, 0, None))
    return p


def _beam(N=50):
    b = np.zeros((N, 4)); b[:, 0] = 1.2; b[:, 3] = 1.2
    return b


def test_feature_shape():
    assert compute_stage1_features(_photons(), _proton(), _beam()).shape == (50, 24)


def test_feature_dtype():
    assert compute_stage1_features(_photons(), _proton(), _beam()).dtype == np.float64


def test_feature_names_count():
    assert len(FEATURE_NAMES_S1) == 24


def test_no_nans():
    X = compute_stage1_features(_photons(), _proton(), _beam())
    assert not np.any(np.isnan(X))


def test_m_gg_nonnegative():
    X = compute_stage1_features(_photons(), _proton(), _beam())
    assert np.all(X[:, :6] >= 0)


def test_e_tot_gamma():
    ph = _photons()
    X = compute_stage1_features(ph, _proton(), _beam())
    col = FEATURE_NAMES_S1.index("E_tot_gamma")
    np.testing.assert_allclose(X[:, col], ph[:, :, 0].sum(axis=1), rtol=1e-9)


def test_n_pairs_near_pi0_integer_in_range():
    X = compute_stage1_features(_photons(), _proton(), _beam())
    col = FEATURE_NAMES_S1.index("n_pairs_near_pi0")
    assert np.all(X[:, col] == np.round(X[:, col]))
    assert np.all((X[:, col] >= 0) & (X[:, col] <= 6))
```

- [ ] **Step 2: Confirm tests fail**

```bash
python -m pytest analysis/ml/tests/test_build_background_features.py -v 2>&1 | head -5
```
Expected: `ImportError`.

- [ ] **Step 3: Implement `analysis/ml/build_background_features.py`**

```python
"""Build stage-1 (signal vs background) feature matrix.

Reads signal MC and background ROOT files, applies photon loss model to
background events, computes 24 global event features, assigns labels and
sample weights from cross_sections.csv, and saves features_stage1.npz.
"""
from __future__ import annotations
import argparse
import csv
import os

import numpy as np
import uproot

from analysis.ml import physics
from analysis.ml.build_features import load_photons as load_signal_photons
from analysis.ml.build_features import load_beam
from analysis.ml.photon_loss import LossParams, apply_loss_events

MP = 0.938272
MPI0 = physics.MPI0
META = physics.META
PI0_WINDOW = 0.030
ETA_WINDOW = 0.060
TARGET = np.array([MP, 0., 0., 0.])

_PAIR_INDICES = [(0,1),(0,2),(0,3),(1,2),(1,3),(2,3)]
_PAIRINGS = [((0,1),(2,3)), ((0,2),(1,3)), ((0,3),(1,2))]

FEATURE_NAMES_S1: list[str] = [
    "m_gg_01", "m_gg_02", "m_gg_03", "m_gg_12", "m_gg_13", "m_gg_23",
    "n_pairs_near_pi0", "n_pairs_near_eta", "best_chi2_pi0eta",
    "E_beam", "E_tot_gamma", "E_proton",
    "missing_mass_sq", "missing_px", "missing_py", "missing_pz", "pt_imbalance",
    "E_max_gamma", "E_min_gamma", "E_rms_gamma",
    "cos_theta_proton_cm", "m_4gamma", "m_2gamma_best_pi0", "m_2gamma_best_eta",
]


def load_bg_photons(root_path: str, n_gamma: int, tree: str = "mc",
                    n_max: int | None = None) -> np.ndarray:
    """Load background photons from ROOT file with g0..g(n_gamma-1) branches.
    Returns (N, n_gamma, 4) [E, px, py, pz]."""
    branches = [f"g{i}" for i in range(n_gamma)]
    t = uproot.open(f"{root_path}:{tree}")
    arrays = t.arrays(branches, entry_stop=n_max, library="ak")
    n = len(arrays[branches[0]])
    out = np.empty((n, n_gamma, 4), dtype=np.float64)
    for i, name in enumerate(branches):
        v = arrays[name]
        out[:, i, 0] = np.asarray(v["fE"])
        out[:, i, 1] = np.asarray(v["fP"]["fX"])
        out[:, i, 2] = np.asarray(v["fP"]["fY"])
        out[:, i, 3] = np.asarray(v["fP"]["fZ"])
    return out


def load_proton_beam(root_path: str, tree: str = "mc",
                     n_max: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (proton (N,4), beam (N,4)) [E,px,py,pz]."""
    t = uproot.open(f"{root_path}:{tree}")
    arrays = t.arrays(["proton", "beam"], entry_stop=n_max, library="ak")
    n = len(arrays["proton"])
    out_p = np.empty((n, 4), dtype=np.float64)
    out_b = np.empty((n, 4), dtype=np.float64)
    for out, name in [(out_p, "proton"), (out_b, "beam")]:
        v = arrays[name]
        out[:, 0] = np.asarray(v["fE"])
        out[:, 1] = np.asarray(v["fP"]["fX"])
        out[:, 2] = np.asarray(v["fP"]["fY"])
        out[:, 3] = np.asarray(v["fP"]["fZ"])
    return out_p, out_b


def compute_stage1_features(
    photons: np.ndarray,
    proton: np.ndarray,
    beam: np.ndarray,
) -> np.ndarray:
    """Compute 24 global event features for stage-1 BDT.

    photons: (N, 4, 4) — [E, px, py, pz]
    proton:  (N, 4)
    beam:    (N, 4)
    Returns: (N, 24) float64
    """
    N = photons.shape[0]

    m_gg = np.stack([
        physics.invariant_mass(photons[:, i], photons[:, j])
        for i, j in _PAIR_INDICES
    ], axis=1)  # (N, 6)

    n_near_pi0 = (np.abs(m_gg - MPI0) < PI0_WINDOW).sum(axis=1).astype(np.float64)
    n_near_eta = (np.abs(m_gg - META) < ETA_WINDOW).sum(axis=1).astype(np.float64)

    chi2s = np.stack([
        physics.chi2_pairing(
            np.minimum(physics.invariant_mass(photons[:, i], photons[:, j]),
                       physics.invariant_mass(photons[:, k], photons[:, l])),
            np.maximum(physics.invariant_mass(photons[:, i], photons[:, j]),
                       physics.invariant_mass(photons[:, k], photons[:, l])),
        )
        for (i, j), (k, l) in _PAIRINGS
    ], axis=1)
    best_chi2 = chi2s.min(axis=1)

    target = np.broadcast_to(TARGET, (N, 4)).copy()
    sum_gamma = photons.sum(axis=1)
    missing = beam + target - proton - sum_gamma
    mm_sq = missing[:, 0]**2 - (missing[:, 1]**2 + missing[:, 2]**2 + missing[:, 3]**2)
    pt_imb = np.sqrt(missing[:, 1]**2 + missing[:, 2]**2)

    E_gamma = photons[:, :, 0]

    W = beam + target
    beta_cm = W[:, 1:] / np.where(W[:, 0:1] > 0, W[:, 0:1], 1.0)
    proton_cm = physics.boost(proton, beta_cm)
    p_mag_cm = np.linalg.norm(proton_cm[:, 1:], axis=1)
    cos_theta_p = proton_cm[:, 3] / np.where(p_mag_cm > 0, p_mag_cm, 1.0)

    e4 = sum_gamma[:, 0]
    p4sq = sum_gamma[:, 1]**2 + sum_gamma[:, 2]**2 + sum_gamma[:, 3]**2
    m_4g = np.sqrt(np.clip(e4**2 - p4sq, 0.0, None))

    m_2g_best_pi0 = m_gg[np.arange(N), np.argmin(np.abs(m_gg - MPI0), axis=1)]
    m_2g_best_eta = m_gg[np.arange(N), np.argmin(np.abs(m_gg - META), axis=1)]

    return np.column_stack([
        m_gg, n_near_pi0, n_near_eta, best_chi2,
        beam[:, 0], E_gamma.sum(axis=1), proton[:, 0],
        mm_sq, missing[:, 1], missing[:, 2], missing[:, 3], pt_imb,
        E_gamma.max(axis=1), E_gamma.min(axis=1),
        np.sqrt(np.mean(E_gamma**2, axis=1)),
        cos_theta_p, m_4g, m_2g_best_pi0, m_2g_best_eta,
    ])


def _load_cross_sections(csv_path: str) -> dict[str, float]:
    with open(csv_path) as f:
        reader = csv.DictReader(r for r in f if not r.startswith("#"))
        return {row["channel"]: float(row["sigma_eff"]) for row in reader}


def _load_signal_proton(root_path: str, n_max: int | None) -> np.ndarray:
    t = uproot.open(f"{root_path}:mc")
    v = t.arrays(["proton"], entry_stop=n_max, library="ak")["proton"]
    out = np.empty((len(v), 4), dtype=np.float64)
    out[:, 0] = np.asarray(v["fE"])
    out[:, 1] = np.asarray(v["fP"]["fX"])
    out[:, 2] = np.asarray(v["fP"]["fY"])
    out[:, 3] = np.asarray(v["fP"]["fZ"])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Build stage-1 feature matrix")
    ap.add_argument("--signal",    default="simulation/eta_pi0_mc.root")
    ap.add_argument("--pi0pi0",    default="simulation/pi0pi0_mc.root")
    ap.add_argument("--pi03",      default="simulation/3pi0_mc.root")
    ap.add_argument("--eta-2pi0",  dest="eta_2pi0", default="simulation/eta_2pi0_mc.root")
    ap.add_argument("--omega-pi0", dest="omega_pi0", default="simulation/omega_pi0_mc.root")
    ap.add_argument("--etaprime",  default="simulation/etaprime_mc.root")
    ap.add_argument("--xsec",      default="simulation/cross_sections.csv")
    ap.add_argument("--output",    default="analysis/ml/data/features_stage1.npz")
    ap.add_argument("--n-max",     type=int, default=None)
    ap.add_argument("--seed",      type=int, default=42)
    args = ap.parse_args()

    params = LossParams()
    rng = np.random.default_rng(args.seed)
    xsec = _load_cross_sections(args.xsec)
    sig_eff = xsec["eta_pi0"]

    all_X, all_y, all_w = [], [], []

    print("Loading signal ...")
    sig_ph = load_signal_photons(args.signal, n_max=args.n_max)
    sig_beam = load_beam(args.signal, n_max=args.n_max)
    sig_proton = _load_signal_proton(args.signal, args.n_max)
    X_sig = compute_stage1_features(sig_ph, sig_proton, sig_beam)
    all_X.append(X_sig)
    all_y.append(np.zeros(len(X_sig), dtype=np.int64))
    all_w.append(np.ones(len(X_sig)))
    print(f"  signal: {len(X_sig)} events")

    bg_configs = [
        ("pi0pi0",    args.pi0pi0,    4, "pi0pi0"),
        ("3pi0",      args.pi03,      6, "3pi0"),
        ("eta_2pi0",  args.eta_2pi0,  6, "eta_2pi0"),
        ("omega_pi0", args.omega_pi0, 5, "omega_pi0"),
        ("etaprime",  args.etaprime,  6, "etaprime"),
    ]

    for label, path, n_gamma, xkey in bg_configs:
        if not os.path.exists(path):
            print(f"  SKIP {label}: {path} not found")
            continue
        print(f"Loading {label} ...")
        bg_ph = load_bg_photons(path, n_gamma, n_max=args.n_max)
        bg_proton, bg_beam = load_proton_beam(path, n_max=args.n_max)
        ph4, idx = apply_loss_events(bg_ph, params, rng)
        X_bg = compute_stage1_features(ph4, bg_proton[idx], bg_beam[idx])
        w = xsec.get(xkey, 1.0) / sig_eff
        all_X.append(X_bg)
        all_y.append(np.ones(len(X_bg), dtype=np.int64))
        all_w.append(np.full(len(X_bg), w))
        print(f"  {label}: {len(bg_ph)} generated -> {len(X_bg)} after loss filter")

    X = np.vstack(all_X)
    y = np.concatenate(all_y)
    w = np.concatenate(all_w)
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    np.savez_compressed(args.output, X=X, y=y, w=w,
                        feature_names=np.array(FEATURE_NAMES_S1))
    print(f"Wrote {args.output}: X={X.shape}, signal_frac={(y==0).mean():.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Confirm tests pass**

```bash
python -m pytest analysis/ml/tests/test_build_background_features.py -v
```
Expected: all 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/build_background_features.py analysis/ml/tests/test_build_background_features.py
git commit -m "feat: add stage-1 feature builder (24 global features, loss filter, xsec weights)"
```

---

## Task 10: Stage-1 BDT Training Script

**Files:**
- Create: `analysis/ml/train_bdt_stage1.py`

**Interfaces:**
- Consumes: `analysis/ml/data/features_stage1.npz` (keys `X`, `y`, `w`, `feature_names`)
- Produces: `analysis/ml/model/bdt_stage1.json`, `analysis/ml/model/stage1_threshold.txt`, 4 plots in `analysis/ml/plots/`

- [ ] **Step 1: Create `analysis/ml/train_bdt_stage1.py`**

```python
"""Train binary stage-1 XGBoost BDT: signal (0) vs background (1)."""
import os
import numpy as np
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, roc_curve

FEATURES   = "analysis/ml/data/features_stage1.npz"
MODEL_OUT  = "analysis/ml/model/bdt_stage1.json"
THRESH_OUT = "analysis/ml/model/stage1_threshold.txt"
PLOT_DIR   = "analysis/ml/plots"
SEED = 42
TARGET_SIG_EFF = 0.95


def main() -> None:
    d = np.load(FEATURES, allow_pickle=True)
    X, y, w = d["X"], d["y"], d["w"]
    names = list(d["feature_names"])

    X_tr, X_te, y_tr, y_te, w_tr, w_te = train_test_split(
        X, y, w, test_size=0.20, random_state=SEED, stratify=y)
    X_tr, X_val, y_tr, y_val, w_tr, w_val = train_test_split(
        X_tr, y_tr, w_tr, test_size=0.25, random_state=SEED, stratify=y_tr)

    model = xgb.XGBClassifier(
        objective="binary:logistic", eval_metric="auc",
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        early_stopping_rounds=25, random_state=SEED, n_jobs=-1)

    model.fit(X_tr, y_tr, sample_weight=w_tr,
              eval_set=[(X_tr, y_tr), (X_val, y_val)],
              sample_weight_eval_set=[w_tr, w_val],
              verbose=False)

    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    model.save_model(MODEL_OUT)

    p_sig = model.predict_proba(X_te)[:, 0]
    auc = roc_auc_score(1 - y_te, p_sig)
    print(f"Stage-1 BDT test AUC: {auc:.4f}")

    fpr, tpr, thresholds = roc_curve(1 - y_te, p_sig)
    idx = np.argmin(np.abs(tpr - TARGET_SIG_EFF))
    chosen = float(thresholds[idx])
    print(f"At {TARGET_SIG_EFF:.0%} sig eff: bkg rejection={1-fpr[idx]:.4f}, threshold={chosen:.4f}")

    with open(THRESH_OUT, "w") as f:
        f.write(f"{chosen:.6f}\n")

    os.makedirs(PLOT_DIR, exist_ok=True)

    plt.figure()
    plt.plot(fpr, tpr, label=f"AUC={auc:.3f}")
    plt.scatter([fpr[idx]], [tpr[idx]], color="red", zorder=5,
                label=f"thr={chosen:.3f} ({TARGET_SIG_EFF:.0%} eff)")
    plt.xlabel("False positive rate"); plt.ylabel("True positive rate")
    plt.title("Stage-1 ROC"); plt.legend(); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/roc_stage1.png", dpi=120); plt.close()

    plt.figure()
    for cls, label in [(0, "signal"), (1, "background")]:
        plt.hist(p_sig[y_te == cls], bins=50, density=True, alpha=0.6, label=label)
    plt.axvline(chosen, color="red", linestyle="--", label=f"thr={chosen:.3f}")
    plt.xlabel("P(signal)"); plt.title("Stage-1 score distribution")
    plt.legend(); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/score_stage1.png", dpi=120); plt.close()

    imp = model.feature_importances_
    idx20 = np.argsort(imp)[::-1][:20]
    plt.figure(figsize=(7, 6))
    plt.barh([names[i] for i in idx20][::-1], imp[idx20][::-1])
    plt.title("Stage-1 top-20 feature importance"); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/feature_importance_stage1.png", dpi=120); plt.close()

    res = model.evals_result()
    plt.figure()
    plt.plot(res["validation_0"]["auc"], label="train")
    plt.plot(res["validation_1"]["auc"], label="val")
    plt.xlabel("round"); plt.ylabel("AUC"); plt.legend()
    plt.title("Stage-1 training curve"); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/training_curve_stage1.png", dpi=120); plt.close()

    print(f"Model: {MODEL_OUT}  Threshold: {THRESH_OUT}  Plots: {PLOT_DIR}/")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test with synthetic data**

```bash
python3 -c "
import numpy as np, os
os.makedirs('analysis/ml/data', exist_ok=True)
rng = np.random.default_rng(0)
N = 2000
X = rng.standard_normal((N, 24))
y = rng.integers(0, 2, N)
w = np.ones(N)
np.savez_compressed('analysis/ml/data/features_stage1.npz',
    X=X, y=y, w=w, feature_names=np.array([f'f{i}' for i in range(24)]))"
python -m analysis.ml.train_bdt_stage1
```
Expected: prints AUC ~0.5 (random data), creates model/threshold/plots without error.

- [ ] **Step 3: Commit**

```bash
git add analysis/ml/train_bdt_stage1.py
git commit -m "feat: add stage-1 binary BDT training script with ROC/score/importance plots"
```

---

## Task 11: Add Stage-1 Gate to Reconstruction

**Files:**
- Modify: `analysis/reconstruct_eta_pi0.py`

**Interfaces:**
- Consumes: `analysis/ml/model/bdt_stage1.json`, `analysis/ml/model/stage1_threshold.txt`, `compute_stage1_features`
- Behaviour: events where `P(signal) < threshold` are skipped before chi2 loop; if model files absent, runs unchanged

The file currently has:
- Line 3-4: `import ROOT`, `import os`, `import numpy as np`, `from array import array`
- Line 40: `combinations = np.loadtxt(combinations_file)`
- Line 118: `for iev in range(n_entries):`
- Line 119: `    chain.GetEntry(iev)`

- [ ] **Step 1: Add imports**

After `from array import array` (line 4), add:

```python
import xgboost as xgb
from analysis.ml.build_background_features import compute_stage1_features
```

- [ ] **Step 2: Load stage-1 model after combinations load**

After `combinations = np.loadtxt(combinations_file)` (line 40), add:

```python
_S1_MODEL  = "analysis/ml/model/bdt_stage1.json"
_S1_THRESH = "analysis/ml/model/stage1_threshold.txt"

_stage1_model = None
_stage1_threshold = 0.5
if os.path.exists(_S1_MODEL):
    _stage1_model = xgb.XGBClassifier()
    _stage1_model.load_model(_S1_MODEL)
    if os.path.exists(_S1_THRESH):
        with open(_S1_THRESH) as _f:
            _stage1_threshold = float(_f.read().strip())
    print(f"Stage-1 BDT loaded (threshold={_stage1_threshold:.4f})")
else:
    print("Stage-1 model not found — stage-1 gate disabled")
```

- [ ] **Step 3: Add gate at top of event loop body**

After `chain.GetEntry(iev)` (line 119), before the reset block, add:

```python
    if _stage1_model is not None and chain.gammas.size() == 4:
        _ph = np.array([[
            chain.gammas[_i].E(), chain.gammas[_i].Px(),
            chain.gammas[_i].Py(), chain.gammas[_i].Pz(),
        ] for _i in range(4)])[np.newaxis, :, :]
        _pr = np.array([[
            chain.protons[0].E()  if chain.protons.size() > 0 else 0.938272,
            chain.protons[0].Px() if chain.protons.size() > 0 else 0.0,
            chain.protons[0].Py() if chain.protons.size() > 0 else 0.0,
            chain.protons[0].Pz() if chain.protons.size() > 0 else 0.0,
        ]])
        _bm = np.array([[chain.beam.E(), 0., 0., chain.beam.E()]])
        if _stage1_model.predict_proba(
            compute_stage1_features(_ph, _pr, _bm)
        )[0, 0] < _stage1_threshold:
            continue
```

- [ ] **Step 4: Verify syntax**

```bash
python3 -c "import ast; ast.parse(open('analysis/reconstruct_eta_pi0.py').read()); print('syntax OK')"
```
Expected: `syntax OK`.

- [ ] **Step 5: Commit**

```bash
git add analysis/reconstruct_eta_pi0.py
git commit -m "feat: add stage-1 BDT gate to reconstruct_eta_pi0.py"
```

---

## Full Pipeline Run Order

```bash
# Generate background MC (in simulation/ directory)
cd simulation
root -l 'generate_pi0pi0_dataset.C(1000000)'
root -l 'generate_3pi0_dataset.C(1000000)'
root -l 'generate_eta_2pi0_dataset.C(1000000)'
root -l 'generate_omega_pi0_dataset.C(1000000)'
root -l 'generate_etaprime_dataset.C(1000000)'
cd ..

# Build stage-1 features
python -m analysis.ml.build_background_features

# Train stage-1 BDT; inspect roc_stage1.png to tune threshold
python -m analysis.ml.train_bdt_stage1
# To override threshold: echo "0.62" > analysis/ml/model/stage1_threshold.txt

# Stage-2 pipeline (unchanged)
python -m analysis.ml.build_features
python -m analysis.ml.train_bdt

# Reconstruction now uses both models
python analysis/reconstruct_eta_pi0.py
```
