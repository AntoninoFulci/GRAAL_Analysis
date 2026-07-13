#define PreAnalysis_cxx

#include "PreAnalysis.h"
#include "CutManager.h"

#include <TCanvas.h>
#include <TH2.h>
#include <TStyle.h>

#include <iostream>
#include <string>
#include <utility>
#include <vector>
#include <Math/Vector4D.h>

#include <TList.h>
#include <TSystem.h>
#include <TSystemDirectory.h>
#include <TSystemFile.h>

using std::pair;
using std::string;
using std::vector;

void PreAnalysis::Loop(std::string output_file) {


   double RMP    = 0.9382720813;
   double RMN    = 0.939485;
   double RMD = 1.877;
   double CLIGHT = 29979245800.; //! cm/sec
   double DIST_WALL;
   int Polarization;
   int RunNumber;

   // Create output file and tree
   TFile *dati = new TFile(output_file.c_str(), "RECREATE");
   TTree *output_tree = new TTree("h80", "Graal data Analysis");

 
   ROOT::Math::PxPyPzEVector beam;
   vector<ROOT::Math::PxPyPzEVector> gammas;
   vector<ROOT::Math::PxPyPzEVector> neutrons;
   vector<ROOT::Math::PxPyPzEVector> protons;
   vector<ROOT::Math::PxPyPzEVector> deuterons;

   // Gamma Angles (Forward neutral tracks identified as photons)
   vector<double> gamma_theta;
   vector<double> gamma_phi;
   
   // Pion Angles (Central and Forward)
   vector<double> pions_theta;
   vector<double> pions_phi;
   
   // Deuteron Angles (Forward)
   vector<double> deuterons_theta;
   vector<double> deuterons_phi;

   // charged (Forward)
   vector<double> fcharged_theta;
   vector<double> fcharged_phi;
   vector<double> fcharged_beta;
   vector<double> fcharged_tof;
   vector<double> fcharded_de;
   

   // Output branches
   output_tree->Branch("beam",    "ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> >", &beam);
   output_tree->Branch("gammas",    "vector<ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> > >", &gammas);
   output_tree->Branch("neutrons",  "vector<ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> > >", &neutrons);
   output_tree->Branch("protons",   "vector<ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> > >", &protons);
   output_tree->Branch("deuterons", "vector<ROOT::Math::LorentzVector<ROOT::Math::PxPyPzE4D<double> > >", &deuterons);
   
   // New, fast angle branches
   output_tree->Branch("gamma_theta", "vector<double>", &gamma_theta);
   output_tree->Branch("gamma_phi",   "vector<double>", &gamma_phi);
   output_tree->Branch("pions_theta", "vector<double>", &pions_theta);
   output_tree->Branch("pions_phi",   "vector<double>", &pions_phi);
   output_tree->Branch("deuterons_theta", "vector<double>", &deuterons_theta);
   output_tree->Branch("deuterons_phi",   "vector<double>", &deuterons_phi);
   output_tree->Branch("fcharged_theta",   "vector<double>", &fcharged_theta);
   output_tree->Branch("fcharged_phi",   "vector<double>", &fcharged_phi);
   output_tree->Branch("fcharged_beta",   "vector<double>", &fcharged_beta);
   output_tree->Branch("fcharged_tof",   "vector<double>", &fcharged_tof);
   output_tree->Branch("fcharded_de",   "vector<double>", &fcharded_de);

   output_tree->Branch("Polarization", &Polarization, "Polarization/I");
   output_tree->Branch("RunNumber", &RunNumber, "RunNumber/I");
   // Check to see if we have a chain
   if (fChain == nullptr) {
      std::cerr << "PreAnalysis::Loop - fChain is null, nothing to do." << std::endl;
      delete dati;
      return;
   }

   Long64_t nentries = fChain->GetEntriesFast();

   for (Long64_t jentry = 0; jentry < nentries; ++jentry) {

      Long64_t ientry = LoadTree(jentry);
      if (ientry < 0) break;
      fChain->GetEntry(jentry);

      // Clear all vectors at the start of the event
      gammas.clear();
      neutrons.clear();
      protons.clear();
      deuterons.clear();
      gamma_theta.clear(); // Clear new vectors
      gamma_phi.clear();   // Clear new vectors
      pions_theta.clear(); // Clear new vectors
      pions_phi.clear();   // Clear new vectors
      deuterons_theta.clear(); // Clear new vectors
      deuterons_phi.clear();   // Clear new vectors
      fcharged_theta.clear();
      fcharged_phi.clear();
      fcharged_beta.clear();
      fcharged_tof.clear();
      fcharded_de.clear();

      beam.SetPxPyPzE(0., 0., Eg_tag_strip[0], Eg_tag_strip[0]);
      Polarization = int(Ipol);
      RunNumber    = Idrun;

      // Central Tracks Loop
      for (int i = 0; i < Nass_3; ++i) {
         double Theta_centr_track_rad   = Thet_centr_track[i] / 180. * M_PI;
         double Phi_centr_track_rad    = Phi_centr_track[i] / 180. * M_PI;

         // Centrally detected neutral tracks
         if (Itipo_track[i] == 11) {
            ROOT::Math::PxPyPzEVector CandidatePhoton;
            CandidatePhoton.SetPxPyPzE(
               Eclusc_track[i] * sin(Theta_centr_track_rad) * cos(Phi_centr_track_rad),
               Eclusc_track[i] * sin(Theta_centr_track_rad) * sin(Phi_centr_track_rad),
               Eclusc_track[i] * cos(Theta_centr_track_rad),
               Eclusc_track[i]);
            gammas.push_back(CandidatePhoton);
         }

         // Centrally detected charged tracks (candidate protons / pions)
         if (Itipo_track[i] == 13 || Itipo_track[i] == 14) {
            TCutG *ProtonCntCut = GetCut("Proton", "Cnt", Idrun, false);

            if (ProtonCntCut != nullptr && ProtonCntCut->IsInside(Eclusc_track[i], Dedx_track[i])) {
               // Proton Candidate
               double Etotpro = Eclusc_track[i] + RMP;
               double Ppro_sq = Etotpro * Etotpro - RMP * RMP;
               
               if (Ppro_sq >= 0) {
                   double Ppro = sqrt(Ppro_sq);
                   ROOT::Math::PxPyPzEVector CandidateProton;
                   CandidateProton.SetPxPyPzE(
                      Ppro * sin(Theta_centr_track_rad) * cos(Phi_centr_track_rad),
                      Ppro * sin(Theta_centr_track_rad) * sin(Phi_centr_track_rad),
                      Ppro * cos(Theta_centr_track_rad),
                      Etotpro);
                   protons.push_back(CandidateProton);
               }
            } 
            else {

               TCutG *PionCntCut = GetCut("Pion", "Cnt", Idrun, false);
               if (PionCntCut != nullptr && PionCntCut->IsInside(Eclusc_track[i], Dedx_track[i])) {

                  // Pion Candidate (Central)
                  pions_theta.push_back(Thet_centr_track[i]); // PUSH THETA
                  pions_phi.push_back(Phi_centr_track[i]);     // PUSH PHI                 
               } 
            }
         }
      }

      // Forward Tracks Loop
      for (int i = 0; i < Nparf; ++i) {

         double Theta_trf_rad = Theta_trf[i] / 180. * M_PI;
         double Phi_trf_rad   = Phi_trf[i] / 180. * M_PI;

         int index_trf_ = 0;
         if (Index_trf[i] != 0) {
            // ROOT arrays start from 0, Fortran from 1
            index_trf_ = Index_trf[i] - 1;
         }
         int index = static_cast<int>(Iass_trf[index_trf_]);

         if (index == 1) { // Neutral Forward Particles
            if (Tof_trf[i] >= 12) { // Neutron Region
               double beta = 335. / (Tof_trf[i] * CLIGHT * 1.E-09);
               if ((1 - beta * beta) > 0) {
                  ROOT::Math::PxPyPzEVector CandidatefNeutron;
                  double gamma       = 1. / sqrt(1 - beta * beta);
                  double ENE_FNeutron = gamma * RMN;
                  double Pfneu_sq     = ENE_FNeutron * ENE_FNeutron - RMN * RMN;
                  if (Pfneu_sq >= 0) {
                      double Pfneu        = sqrt(Pfneu_sq);
                      CandidatefNeutron.SetPxPyPzE(
                         Pfneu * sin(Theta_trf_rad) * cos(Phi_trf_rad),
                         Pfneu * sin(Theta_trf_rad) * sin(Phi_trf_rad),
                         Pfneu * cos(Theta_trf_rad),
                         ENE_FNeutron);
                      neutrons.push_back(CandidatefNeutron);
                  }
               }
            } else if (Tof_trf[i] >= 7.5 && Tof_trf[i] <= 12.5) { // Photon Region
               // Photon Angle Candidate (Forward)
               gamma_theta.push_back(Theta_trf[i]); // PUSH THETA
               gamma_phi.push_back(Phi_trf[i]);     // PUSH PHI
            }
         }

         // Charged Forward Particles
         if (index != 1) {
            if (index == 5) {
               DIST_WALL = 335.; // in cm
            } else {
               DIST_WALL = 301.53;
            }

            if (!( Idrun > 4577 && Idrun < 4606)) { // 2005_d1 run range
                  double beta    = DIST_WALL / (Tof_trf[i] * CLIGHT * 1.E-09);
                  fcharged_theta.push_back(Theta_trf_rad);
                  fcharged_phi.push_back(Phi_trf_rad);
                  fcharged_beta.push_back(beta);
                  fcharged_tof.push_back(Tof_trf[i]);
                  fcharded_de.push_back(De_trf[i]);

               // Proton Forward Region
               TCutG *ProtonFwdCut = GetCut("Proton", "Fwd", Idrun, false);
               if (ProtonFwdCut != nullptr && ProtonFwdCut->IsInside(Tof_trf[i], De_trf[i])) {

                  if ((1 - beta * beta) > 0) {
                     ROOT::Math::PxPyPzEVector CandidatefProton;
                     double gamma        = 1. / sqrt(1 - beta * beta);
                     double ENE_FPROTON  = gamma * RMP;
                     double Pfpro_sq     = ENE_FPROTON * ENE_FPROTON - RMP * RMP;
                     if (Pfpro_sq >= 0) {
                         double Pfpro        = sqrt(Pfpro_sq);
                         CandidatefProton.SetPxPyPzE(
                            Pfpro * sin(Theta_trf_rad) * cos(Phi_trf_rad ),
                            Pfpro * sin(Theta_trf_rad) * sin(Phi_trf_rad ),
                            Pfpro * cos(Theta_trf_rad),
                            ENE_FPROTON);
                         protons.push_back(CandidatefProton);
                     }
                  }
               }

               // Pion Forward Region
               TCutG *PionFwdCut = GetCut("Pion", "Fwd", Idrun, false);
               if (PionFwdCut != nullptr && PionFwdCut->IsInside(Tof_trf[i], De_trf[i])) {
                  // Pion Angle Candidate (Forward)
                  pions_theta.push_back(Theta_trf[i]); // PUSH THETA
                  pions_phi.push_back(Phi_trf[i]);     // PUSH PHI
               }

               // Deuteron Forward Region
               TCutG *DeuteronCut = GetCut("Deuteron", "Fwd", Idrun, false);
               if (DeuteronCut  != nullptr && DeuteronCut ->IsInside(Tof_trf[i], De_trf[i])) {
                  
                  // Deuteron Angle Candidate (Forward)
                  deuterons_theta.push_back(Theta_trf[i]); // PUSH THETA
                  deuterons_phi.push_back(Phi_trf[i]);     // PUSH PHI
                  
                  if ((1 - beta * beta) > 0) {
                     ROOT::Math::PxPyPzEVector CandidatefDeu;
                     double gamma          = 1. / sqrt(1 - beta * beta);
                     double ENE_FDEUTERON  = gamma * RMD; // energia totale
                     double Pfdeu_sq       = ENE_FDEUTERON * ENE_FDEUTERON - RMD * RMD;
                     if (Pfdeu_sq >= 0) {
                         double Pfdeu          = sqrt(Pfdeu_sq);
                         CandidatefDeu.SetPxPyPzE(
                            Pfdeu * sin(Theta_trf_rad) * cos(Phi_trf_rad ),
                            Pfdeu * sin(Theta_trf_rad) * sin(Phi_trf_rad ),
                            Pfdeu * cos(Theta_trf_rad),
                            ENE_FDEUTERON);
                            deuterons.push_back(CandidatefDeu);
                     }
                  }
               }
            }
         }
      }

      // Basic event selection and fill of the output tree
      output_tree->Fill();
   }

   output_tree->Write("", TObject::kOverwrite);  // reuse the key, avoid extra ;N cycles
   dati->Close();

}

// Convenience wrapper to run the analysis from ROOT
void PreAnalysis(string input = "", string output = "pre_analisi.root") {

   if (input == "") {
      std::cerr << "!!! PreAnalysis: No input files specified." << std::endl;
      return;
   }

   // Branches to enable
   std::vector<std::string> branches{"Eg_tag_strip",
      "Idrun","Ipol", 
      "Nass_3", 
      "Thet_centr_track", 
      "Phi_centr_track", 
      "Itipo_track", 
      "Eclusc_track", 
      "Dedx_track", 
      "Nparf",      
      "Theta_trf", 
      "Phi_trf", 
      "Index_trf",  
      "Iass_trf",   
      "Tof_trf", 
      "De_trf"      
   };

   class PreAnalysis t(input, branches);

   std::cout << "Beginning analysis..." << std::endl;
   t.Loop(output);
   std::cout << "Finished" << std::endl;
}

void AnalyzeAll(const std::string &base_in = "/data/graal/graal_data",
                const std::string &base_out = "/data/graal/pre_analisi") {
   // One output ROOT file per subdirectory:
   // /data/graal/pre_analisi/pre_analisi_<run_name>.root

   gSystem->mkdir(base_out.c_str(), true);

   // Build the cut map once (faster than doing it for every folder).
   // Keep current "cuts" location relative unless you want it absolute.
   BuildCutMap((base_in + "/").c_str(), "./cuts");
   PrintCutMap();

   TSystemDirectory baseDir("graal_data", base_in.c_str());
   TList *entries = baseDir.GetListOfFiles();
   if (!entries) {
      std::cerr << "AnalyzeAll: cannot list directory: " << base_in << std::endl;
      return;
   }

   entries->Sort(); // nicer/consistent ordering

   TIter next(entries);
   while (TObject *obj = next()) {
      auto *f = dynamic_cast<TSystemFile *>(obj);
      if (!f) continue;

      const std::string name = f->GetName();
      if (name == "." || name == "..") continue;
      if (!f->IsDirectory()) continue;

      const std::string in_pattern = base_in + "/" + name + "/*.root";
      const std::string out_file = base_out + "/pre_analisi_" + name + ".root";

      std::cout << "==> " << name << std::endl;
      std::cout << "    input:  " << in_pattern << std::endl;
      std::cout << "    output: " << out_file << std::endl;

      PreAnalysis(in_pattern, out_file);
   }
}
