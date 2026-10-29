"""
analyze_eta_pi0.py
------------------
Scheletro PyROOT per l'analisi di reco_eta_pi0_bdt.root.

Struttura del TTree "reco_eta_pi0_bdt" (147854 entries):
  Scalari  : chi2, eta_mass, pi0_mass, bdt_score, Xstrip  (float)
             RunNumber, Polarization, n_photons_input      (int)
  TLVs     : beam, target, proton, neutron, eta,
             eta_gamma1, eta_gamma2,
             pi0, pi0_gamma1, pi0_gamma2, missing
"""

import ROOT
import sys

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------
INPUT_FILES = [
    "reco_eta_pi0_bdt.root",
    "reco_eta_pi0_bdt_vis.root"
]

TREE_NAME   = "reco_eta_pi0_bdt"
OUTPUT_FILE = "histograms_output.root"

ROOT.gROOT.SetBatch(True)          # niente finestre interattive
ROOT.gStyle.SetOptStat("emr")      # entries / media / rms nel box delle stat
ROOT.gStyle.SetOptFit(1111)        # risultati del fit nel box

ROOT.gStyle.SetPadTopMargin(0.1);     # Set Margin Top
ROOT.gStyle.SetPadRightMargin(0.05);   # Set Margin Right
ROOT.gStyle.SetPadBottomMargin(0.15);    # Set Margin Bottom
ROOT.gStyle.SetPadLeftMargin(0.12);     # Set Margin Left
ROOT.gStyle.SetTitleXOffset(1.0)
ROOT.gStyle.SetTitleYOffset(0.8)
ROOT.TGaxis.SetMaxDigits(3)

# ---------------------------------------------------------------------------
# Catena dei file di input
# ---------------------------------------------------------------------------

tree = ROOT.TChain(TREE_NAME)

for filename in INPUT_FILES:

    # Controllo preliminare del file
    f = ROOT.TFile.Open(filename, "READ")

    if not f or f.IsZombie():
        sys.exit(f"[ERRORE] Impossibile aprire {filename}")

    if not f.Get(TREE_NAME):
        sys.exit(
            f"[ERRORE] TTree '{TREE_NAME}' "
            f"non trovato in {filename}"
        )

    f.Close()

    # Aggiunge il file alla catena
    tree.Add(filename)

    print(f"[INFO] Aggiunto: {filename}")


print(
    f"[INFO] Totale: {tree.GetEntries()} eventi "
    f"nel TChain '{TREE_NAME}'"
)

# Definizione degli istogrammi
# ---------------------------------------------------------------------------
# ---- eta->Theta() in gradi --------------------------------------------------
h_theta_missp_deg = ROOT.TH1F(
    "h_theta_missp_deg",
    "# ;#theta_{missing #eta#pi}-#theta_{proton} [deg];Conteggi",
    100, -10.0, 10.0        # adatta il range se necessario
)

# ---- eta_mass ---------------------------------------------------------------
h_eta_mass = ROOT.TH1F(
    "h_eta_mass",
    "Massa invariante #eta;M_{#eta} [GeV/c^{2}];Conteggi",
    100, 0.4, 0.7         # range intorno al picco dell'eta (547 MeV)
)

# ---- pi0_mass ---------------------------------------------------------------
h_pi0_mass = ROOT.TH1F(
    "h_pi0_mass",
    "Massa invariante #pi^{0};M_{#pi^{0}} [GeV/c^{2}];Conteggi",
    100, 0.08, 0.18       # range intorno al picco del pi0 (135 MeV)
)

# ---- Coplenarità in gradi --------------------------------------------------
h_coplanarity_deg = ROOT.TH1F(
    "h_coplanarity_deg",
    ";Coplanarity_{proton-#eta#pi} [deg];Conteggi",
    100, -10.0, 10.0        # adatta il range se necessario
)

# ---- Miss mass to proton -------------------------------------------------------------------
h_mass_missp_gev = ROOT.TH1F(
    "h_mass_missp_gev",
    "# ;M_{missing #eta#pi} [GeV];Conteggi",
    100, 0.8, 1.1        # adatta il range se necessario
)

# ---- egamma vs theta proto (2-D) --------------------------------------------
h2_theta_mass = ROOT.TH2F(
    "h2_eta_theta_vs_mass",
    ";#theta_{proton} [deg];E_{#gamma} [GeV/c^{2}]",
    50, 0.0, 40.0,
    50, 0.9, 1.55
)

# ---- aggiungi altri istogrammi qui -----------------------------------------
# Esempio: impulso trasverso dell'eta
# h_eta_pt = ROOT.TH1F("h_eta_pt", "p_{T}(#eta);p_{T} [GeV/c];Conteggi", 100, 0, 2)


# ---------------------------------------------------------------------------
# Loop sugli eventi
# ---------------------------------------------------------------------------
n_entries = tree.GetEntries()
print(f"[INFO] Avvio loop su {n_entries} eventi…")

for i, event in enumerate(tree):
    # progresso ogni 10% degli eventi
    if i % (n_entries//10) == 0:
        print(f"  {round(100 * i / n_entries)}% completato")

    # --- Accesso ai branch TLorentzVector -----------------------------------
    target_tlv = event.target                # TLorentzVector
    beam_tlv = event.beam                 # TLorentzVector
    eta_tlv = event.eta                 # TLorentzVector
    pi0_tlv = event.pi0                 # TLorentzVector
    proton_tlv = event.proton                 # TLorentzVector
    missing_tlv = event.missing                 # TLorentzVector

    theta_missp_deg = ROOT.TMath.RadToDeg() * (missing_tlv.Theta()-proton_tlv.Theta())
    missm = (target_tlv+beam_tlv-eta_tlv-pi0_tlv).M()
    # --- Riempimento istogrammi ---------------------------------------------
    h_theta_missp_deg.Fill(theta_missp_deg)
    h_eta_mass .Fill(event.eta_mass)
    h_pi0_mass .Fill(event.pi0_mass)
    h_coplanarity_deg.Fill(theta_missp_deg)
    h_mass_missp_gev.Fill(missm)
    h2_theta_mass.Fill(proton_tlv.Theta()*ROOT.TMath.RadToDeg(),beam_tlv.E())

    # --- Eventuale taglio di selezione (decommentare per applicarlo) --------
    # if event.bdt_score < 0.1:
    #     continue

    # --- Altri branch disponibili (esempi) ----------------------------------
    # event.proton         -> TLorentzVector del protone
    # event.pi0            -> TLorentzVector del pi0
    # event.eta_gamma1     -> TLorentzVector del primo fotone dell'eta
    # event.n_photons_input, event.Xstrip, event.RunNumber, event.Polarization

print("[INFO] Loop terminato.")


# ---------------------------------------------------------------------------
# Fit gaussiano sull'eta_mass
# ---------------------------------------------------------------------------
fit_result = h_eta_mass.Fit("gaus", "S Q", "", 0.50, 0.60)   # "S"=salva, "Q"=silenzioso
if fit_result and fit_result.IsValid():
    print(f"[FIT] eta_mass: mu = {fit_result.Parameter(1):.4f} GeV"
          f"  sigma = {fit_result.Parameter(2)*1000:.1f} MeV")


# ---------------------------------------------------------------------------
# Salvataggio delle figure
# ---------------------------------------------------------------------------
fout = ROOT.TFile.Open(OUTPUT_FILE, "RECREATE")
if not fout or fout.IsZombie():
    sys.exit(f"[ERRORE] Impossibile creare {OUTPUT_FILE}")

# --- Scrivi tutti gli istogrammi nel file di output -------------------------
for h in [h_theta_missp_deg, h_eta_mass, h_pi0_mass, h_coplanarity_deg, h_mass_missp_gev, h2_theta_mass]:
    h.Write()

# --- Esporta anche come PNG (opzionale) -------------------------------------
canvas = ROOT.TCanvas("c1", "c1", 600, 500)
plots = [
    (h_theta_missp_deg, "h_theta_missp_deg.png", "HIST"),
    (h_eta_mass,  "h_eta_mass.png",  "E"),
    (h_pi0_mass,  "h_pi0_mass.png",  "E"),
    (h_coplanarity_deg,       "h_coplanarity_deg.png", "HIST"),
    (h_mass_missp_gev,      "h_mass_missp_gev.png",      "HIST"),
    (h2_theta_mass, "h2_theta_vs_mass.png", "COLZ"),
]

for h, fname, drawopt in plots:
    canvas.Clear()
    h.Draw(drawopt)
    h.GetXaxis().CenterTitle()
    h.GetYaxis().CenterTitle()
    canvas.SaveAs(fname)
    print(f"[SAVE] {fname}")

fout.Close()
print(f"[DONE] Istogrammi salvati in '{OUTPUT_FILE}'")
