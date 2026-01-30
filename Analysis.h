//////////////////////////////////////////////////////////
// This class has been automatically generated on
// Mon Jul 26 19:57:33 2021 by ROOT version 6.22/02
// from TTree h70/
// found on file: run1515.root
//////////////////////////////////////////////////////////

#ifndef Analysis_h
#define Analysis_h

#include <TROOT.h>
#include <TChain.h>
#include <TFile.h>
#include <dirent.h>
#include <sys/stat.h>


// Header file for the classes stored in the TTree if any.

class Analysis {
public :
   TTree          *fChain;   //!pointer to the analyzed TTree or TChain
   Int_t           fCurrent; //!current Tree number in a TChain

// Fixed size dimensions of array or collections stored in the TTree if any.

   // Declaration of leaf types
   UInt_t          Idrun;
   UInt_t          Idevt;
   UInt_t          Ipol;
   UChar_t         Itrig;
   UInt_t          Nphys;
   Int_t           Mplastic;
   UChar_t         Iplastic[15];   //[Mplastic]
   Float_t         Eg_tag_pm[15];   //[Mplastic]
   Char_t          Ind_bunch_rf;
   Int_t           Mpm_bad;
   UChar_t         Ipm_bad[15];   //[Mpm_bad]
   Int_t           Ncstrip;
   UChar_t         Mstrip[128];   //[Ncstrip]
   Float_t         Xstrip[128];   //[Ncstrip]
   Float_t         Eg_tag_strip[128];   //[Ncstrip]
   UChar_t         Iflag_strip;
   Int_t           Ncstrip_bad;
   UChar_t         Mstrip_bad[128];   //[Ncstrip_bad]
   Float_t         Xstrip_bad[128];   //[Ncstrip_bad]
   Float_t         Eg_tag_s_bad[128];   //[Ncstrip_bad]
   Int_t           Nbclus;
   Char_t          Mclus[30];   //[Nbclus]
   Float_t         Eclus[30];   //[Nbclus]
   Float_t         Tetclus[30];   //[Nbclus]
   Float_t         Phiclus[30];   //[Nbclus]
   Float_t         Eclusc[30];   //[Nbclus]
   Float_t         Tetclusc[30];   //[Nbclus]
   Float_t         Phiclusc[30];   //[Nbclus]
   Char_t          Ind_bgo[30];   //[Nbclus]
   Float_t         Emax[30];   //[Nbclus]
   Float_t         Sx1[30];   //[Nbclus]
   Float_t         Sy1[30];   //[Nbclus]
   Float_t         Sx2[30];   //[Nbclus]
   Float_t         Sy2[30];   //[Nbclus]
   Int_t           Ifl[30];   //[Nbclus]
   Int_t           Nass_2;
   Int_t           Iass_2[130][2];   //[Nass_2]
   Int_t           Nass_3;
   Int_t           Iass_3[291][3];   //[Nass_3]
   Int_t           Itipo_track[291];   //[Nass_3]
   UChar_t         I_bar_track[291];   //[Nass_3]
   Float_t         Dedx_track[291];   //[Nass_3]
   Float_t         T_bar_track[291];   //[Nass_3]
   Char_t          Ind_bar_track[291];   //[Nass_3]
   Float_t         Phi_bar_track[291];   //[Nass_3]
   Float_t         Eclusc_track[291];   //[Nass_3]
   Float_t         Thet_bgo_track[291];   //[Nass_3]
   Float_t         Phi_bgo_track[291];   //[Nass_3]
   Float_t         Thet_cyl_track[291];   //[Nass_3]
   Float_t         Phi_cyl_track[291];   //[Nass_3]
   Float_t         Thet_centr_track[291];   //[Nass_3]
   Float_t         Phi_centr_track[291];   //[Nass_3]
   Int_t           Nbclus_sp;
   Char_t          Mclus_sp[30];   //[Nbclus_sp]
   Float_t         Eclus_sp[30];   //[Nbclus_sp]
   Float_t         Tetclus_sp[30];   //[Nbclus_sp]
   Float_t         Phiclus_sp[30];   //[Nbclus_sp]
   Float_t         Eclusc_sp[30];   //[Nbclus_sp]
   Float_t         Tetclusc_sp[30];   //[Nbclus_sp]
   Float_t         Phiclusc_sp[30];   //[Nbclus_sp]
   Int_t           Nbar;
   UChar_t         Ibar[32];   //[Nbar]
   Float_t         Ebar[32];   //[Nbar]
   Float_t         Timbar[32];   //[Nbar]
   Char_t          Ind_bar[32];   //[Nbar]
   UChar_t         Nbarc;
   Int_t           Mhtbgo;
   UChar_t         Ihtbgo[15];   //[Mhtbgo]
   UShort_t        Htbgo[15];   //[Mhtbgo]
   UShort_t        Ttot;
   UChar_t         Lpm_b_b;
   UChar_t         Lanabar;
   UChar_t         Lanabgo;
   UChar_t         Lanamatch;
   UChar_t         Lpm0;
   Int_t           Ntra;
   Float_t         A1[20];   //[Ntra]
   Float_t         A2[20];   //[Ntra]
   Float_t         A3[20];   //[Ntra]
   Float_t         B1[20];   //[Ntra]
   Float_t         B2[20];   //[Ntra]
   Float_t         B3[20];   //[Ntra]
   Float_t         De[20];   //[Ntra]
   Float_t         Tf[20];   //[Ntra]
   UChar_t         Icol1[20];   //[Ntra]
   UChar_t         Icol2[20];   //[Ntra]
   UChar_t         Cl1[20];   //[Ntra]
   Char_t          Cltot1;
   Int_t           Lm_1;
   Int_t           Ip1_cor[3];   //[Lm_1]
   Float_t         Ene_l[3];   //[Lm_1]
   Float_t         Ene_r[3];   //[Lm_1]
   Float_t         Tof_l[3];   //[Lm_1]
   Float_t         Tof_r[3];   //[Lm_1]
   Float_t         Delta_tof_h[3];   //[Lm_1]
   Float_t         Amean_tof_h[3];   //[Lm_1]
   Float_t         T_lr[3];   //[Lm_1]
   Float_t         A_tof1[3];   //[Lm_1]
   Float_t         A_de1[3];   //[Lm_1]
   Float_t         X_w1[3];   //[Lm_1]
   Float_t         Y_w1[3];   //[Lm_1]
   Char_t          Iass_w1[3];   //[Lm_1]
   Int_t           Lm_2;
   UChar_t         Ip2_cor[3];   //[Lm_2]
   Float_t         Ene_u[3];   //[Lm_2]
   Float_t         Ene_d[3];   //[Lm_2]
   Float_t         Tof_u[3];   //[Lm_2]
   Float_t         Tof_d[3];   //[Lm_2]
   Float_t         Delta_tof_v[3];   //[Lm_2]
   Float_t         Amean_tof_v[3];   //[Lm_2]
   Float_t         T_ud[3];   //[Lm_2]
   Float_t         A_tof2[3];   //[Lm_2]
   Float_t         A_de2[3];   //[Lm_2]
   Float_t         X_w2[3];   //[Lm_2]
   Float_t         Y_w2[3];   //[Lm_2]
   Char_t          Iass_w2[3];   //[Lm_2]
   Int_t           M_wal;
   Float_t         Wal_par[24][8];   //[M_wal]
   UChar_t         Ind_par[24][4];   //[M_wal]
   Float_t         Theta_w[24];   //[M_wal]
   Float_t         Phi_w[24];   //[M_wal]
   Char_t          Ind_wal[5];
   Char_t          Iass_track[24];   //[M_wal]
   Int_t           Nppln2;
   Float_t         U_pc[20];   //[Nppln2]
   Float_t         V_pc[20];   //[Nppln2]
   Float_t         X_pc[20];   //[Nppln2]
   Float_t         Y_pc[20];   //[Nppln2]
   Int_t           N_traf;
   UChar_t         Ind_traf[90][3];   //[N_traf]
   UChar_t         Iass_trf[90];   //[N_traf]
   UChar_t         Iforw_c;
   UChar_t         Iforw_n;
   Int_t           Nparf;
   UChar_t         Nparf_c;
   UChar_t         Nparf_n;
   UChar_t         Nparf_strange;
   Float_t         Cos_trf[90][3];   //[Nparf]
   Float_t         Theta_trf[90];   //[Nparf]
   Float_t         Phi_trf[90];   //[Nparf]
   Float_t         Tof_trf[90];   //[Nparf]
   Float_t         De_trf[90];   //[Nparf]
   UChar_t         Index_trf[90];   //[Nparf]
   UChar_t         Info_wal[90];   //[Nparf]
   Int_t           Nshow;
   Float_t         Eshow[16];   //[Nshow]
   Float_t         Tshow[16];   //[Nshow]
   Float_t         Yshow[16];   //[Nshow]
   Float_t         Xshow[16];   //[Nshow]
   Float_t         Tetshow[16];   //[Nshow]
   Float_t         Phishow[16];   //[Nshow]
   Float_t         Tshpc[16];   //[Nshow]
   Float_t         Pshpc[16];   //[Nshow]
   Int_t           Typeshow[16];   //[Nshow]
   Int_t           N_ur;
   Int_t           Nsh_ur[16];   //[N_ur]
   Float_t         Esh_ur[16];   //[N_ur]
   Float_t         Ts_ur[16];   //[N_ur]
   Int_t           Nb_traces_cyl;
   Float_t         Dz_trace_int[5];   //[Nb_traces_cyl]
   Float_t         Dz_trace_ext[5];   //[Nb_traces_cyl]
   Float_t         X_trace_int[5];   //[Nb_traces_cyl]
   Float_t         Y_trace_int[5];   //[Nb_traces_cyl]
   Float_t         Z_trace_int[5];   //[Nb_traces_cyl]
   Float_t         X_trace_ext[5];   //[Nb_traces_cyl]
   Float_t         Y_trace_ext[5];   //[Nb_traces_cyl]
   Float_t         Z_trace_ext[5];   //[Nb_traces_cyl]
   Float_t         Dphi_trace_cyl[5];   //[Nb_traces_cyl]
   Float_t         Teta_trace_cyl[5];   //[Nb_traces_cyl]
   Float_t         Phi_trace_cyl[5];   //[Nb_traces_cyl]
   Float_t         Z_trace_cyl[5];   //[Nb_traces_cyl]
   UShort_t        Status_traces_cyl;
   Int_t           Lctdb;
   UShort_t        Ictdb[12];   //[Lctdb]
   UShort_t        Ectdb[12];   //[Lctdb]
   UShort_t        Tctdb[12];   //[Lctdb]
   Int_t           Lctdf;
   UShort_t        Ictdf[12];   //[Lctdf]
   UShort_t        Ectdf[12];   //[Lctdf]
   UShort_t        Tctdf[12];   //[Lctdf]

   // List of branches
   TBranch        *b_Idrun;   //!
   TBranch        *b_Idevt;   //!
   TBranch        *b_Ipol;   //!
   TBranch        *b_Itrig;   //!
   TBranch        *b_Nphys;   //!
   TBranch        *b_Mplastic;   //!
   TBranch        *b_Iplastic;   //!
   TBranch        *b_Eg_tag_pm;   //!
   TBranch        *b_Ind_bunch_rf;   //!
   TBranch        *b_Mpm_bad;   //!
   TBranch        *b_Ipm_bad;   //!
   TBranch        *b_Ncstrip;   //!
   TBranch        *b_Mstrip;   //!
   TBranch        *b_Xstrip;   //!
   TBranch        *b_Eg_tag_strip;   //!
   TBranch        *b_Iflag_strip;   //!
   TBranch        *b_Ncstrip_bad;   //!
   TBranch        *b_Mstrip_bad;   //!
   TBranch        *b_Xstrip_bad;   //!
   TBranch        *b_Eg_tag_s_bad;   //!
   TBranch        *b_Nbclus;   //!
   TBranch        *b_Mclus;   //!
   TBranch        *b_Eclus;   //!
   TBranch        *b_Tetclus;   //!
   TBranch        *b_Phiclus;   //!
   TBranch        *b_Eclusc;   //!
   TBranch        *b_Tetclusc;   //!
   TBranch        *b_Phiclusc;   //!
   TBranch        *b_Ind_bgo;   //!
   TBranch        *b_Emax;   //!
   TBranch        *b_Sx1;   //!
   TBranch        *b_Sy1;   //!
   TBranch        *b_Sx2;   //!
   TBranch        *b_Sy2;   //!
   TBranch        *b_Ifl;   //!
   TBranch        *b_Nass_2;   //!
   TBranch        *b_Iass_2;   //!
   TBranch        *b_Nass_3;   //!
   TBranch        *b_Iass_3;   //!
   TBranch        *b_Itipo_track;   //!
   TBranch        *b_I_bar_track;   //!
   TBranch        *b_Dedx_track;   //!
   TBranch        *b_T_bar_track;   //!
   TBranch        *b_Ind_bar_track;   //!
   TBranch        *b_Phi_bar_track;   //!
   TBranch        *b_Eclusc_track;   //!
   TBranch        *b_Thet_bgo_track;   //!
   TBranch        *b_Phi_bgo_track;   //!
   TBranch        *b_Thet_cyl_track;   //!
   TBranch        *b_Phi_cyl_track;   //!
   TBranch        *b_Thet_centr_track;   //!
   TBranch        *b_Phi_centr_track;   //!
   TBranch        *b_Nbclus_sp;   //!
   TBranch        *b_Mclus_sp;   //!
   TBranch        *b_Eclus_sp;   //!
   TBranch        *b_Tetclus_sp;   //!
   TBranch        *b_Phiclus_sp;   //!
   TBranch        *b_Eclusc_sp;   //!
   TBranch        *b_Tetclusc_sp;   //!
   TBranch        *b_Phiclusc_sp;   //!
   TBranch        *b_Nbar;   //!
   TBranch        *b_Ibar;   //!
   TBranch        *b_Ebar;   //!
   TBranch        *b_Timbar;   //!
   TBranch        *b_Ind_bar;   //!
   TBranch        *b_Nbarc;   //!
   TBranch        *b_Mhtbgo;   //!
   TBranch        *b_Ihtbgo;   //!
   TBranch        *b_Htbgo;   //!
   TBranch        *b_Ttot;   //!
   TBranch        *b_Lpm_b_b;   //!
   TBranch        *b_Lanabar;   //!
   TBranch        *b_Lanabgo;   //!
   TBranch        *b_Lanamatch;   //!
   TBranch        *b_Lpm0;   //!
   TBranch        *b_Ntra;   //!
   TBranch        *b_A1;   //!
   TBranch        *b_A2;   //!
   TBranch        *b_A3;   //!
   TBranch        *b_B1;   //!
   TBranch        *b_B2;   //!
   TBranch        *b_B3;   //!
   TBranch        *b_De;   //!
   TBranch        *b_Tf;   //!
   TBranch        *b_Icol1;   //!
   TBranch        *b_Icol2;   //!
   TBranch        *b_Cl1;   //!
   TBranch        *b_Cltot1;   //!
   TBranch        *b_Lm_1;   //!
   TBranch        *b_Ip1_cor;   //!
   TBranch        *b_Ene_l;   //!
   TBranch        *b_Ene_r;   //!
   TBranch        *b_Tof_l;   //!
   TBranch        *b_Tof_r;   //!
   TBranch        *b_Delta_tof_h;   //!
   TBranch        *b_Amean_tof_h;   //!
   TBranch        *b_T_lr;   //!
   TBranch        *b_A_tof1;   //!
   TBranch        *b_A_de1;   //!
   TBranch        *b_X_w1;   //!
   TBranch        *b_Y_w1;   //!
   TBranch        *b_Iass_w1;   //!
   TBranch        *b_Lm_2;   //!
   TBranch        *b_Ip2_cor;   //!
   TBranch        *b_Ene_u;   //!
   TBranch        *b_Ene_d;   //!
   TBranch        *b_Tof_u;   //!
   TBranch        *b_Tof_d;   //!
   TBranch        *b_Delta_tof_v;   //!
   TBranch        *b_Amean_tof_v;   //!
   TBranch        *b_T_ud;   //!
   TBranch        *b_A_tof2;   //!
   TBranch        *b_A_de2;   //!
   TBranch        *b_X_w2;   //!
   TBranch        *b_Y_w2;   //!
   TBranch        *b_Iass_w2;   //!
   TBranch        *b_M_wal;   //!
   TBranch        *b_Wal_par;   //!
   TBranch        *b_Ind_par;   //!
   TBranch        *b_Theta_w;   //!
   TBranch        *b_Phi_w;   //!
   TBranch        *b_Ind_wal;   //!
   TBranch        *b_Iass_track;   //!
   TBranch        *b_Nppln2;   //!
   TBranch        *b_U_pc;   //!
   TBranch        *b_V_pc;   //!
   TBranch        *b_X_pc;   //!
   TBranch        *b_Y_pc;   //!
   TBranch        *b_N_traf;   //!
   TBranch        *b_Ind_traf;   //!
   TBranch        *b_Iass_trf;   //!
   TBranch        *b_Iforw_c;   //!
   TBranch        *b_Iforw_n;   //!
   TBranch        *b_Nparf;   //!
   TBranch        *b_Nparf_c;   //!
   TBranch        *b_Nparf_n;   //!
   TBranch        *b_Nparf_strange;   //!
   TBranch        *b_Cos_trf;   //!
   TBranch        *b_Theta_trf;   //!
   TBranch        *b_Phi_trf;   //!
   TBranch        *b_Tof_trf;   //!
   TBranch        *b_De_trf;   //!
   TBranch        *b_Index_trf;   //!
   TBranch        *b_Info_wal;   //!
   TBranch        *b_Nshow;   //!
   TBranch        *b_Eshow;   //!
   TBranch        *b_Tshow;   //!
   TBranch        *b_Yshow;   //!
   TBranch        *b_Xshow;   //!
   TBranch        *b_Tetshow;   //!
   TBranch        *b_Phishow;   //!
   TBranch        *b_Tshpc;   //!
   TBranch        *b_Pshpc;   //!
   TBranch        *b_Typeshow;   //!
   TBranch        *b_N_ur;   //!
   TBranch        *b_Nsh_ur;   //!
   TBranch        *b_Esh_ur;   //!
   TBranch        *b_Ts_ur;   //!
   TBranch        *b_Nb_traces_cyl;   //!
   TBranch        *b_Dz_trace_int;   //!
   TBranch        *b_Dz_trace_ext;   //!
   TBranch        *b_X_trace_int;   //!
   TBranch        *b_Y_trace_int;   //!
   TBranch        *b_Z_trace_int;   //!
   TBranch        *b_X_trace_ext;   //!
   TBranch        *b_Y_trace_ext;   //!
   TBranch        *b_Z_trace_ext;   //!
   TBranch        *b_Dphi_trace_cyl;   //!
   TBranch        *b_Teta_trace_cyl;   //!
   TBranch        *b_Phi_trace_cyl;   //!
   TBranch        *b_Z_trace_cyl;   //!
   TBranch        *b_Status_traces_cyl;   //!
   TBranch        *b_Lctdb;   //!
   TBranch        *b_Ictdb;   //!
   TBranch        *b_Ectdb;   //!
   TBranch        *b_Tctdb;   //!
   TBranch        *b_Lctdf;   //!
   TBranch        *b_Ictdf;   //!
   TBranch        *b_Ectdf;   //!
   TBranch        *b_Tctdf;   //!

   //template aggiunto per calcolare facilmente il tempo di esecuzione di una task
   template <
       class result_t   = std::chrono::seconds,
       class clock_t    = std::chrono::steady_clock,
       class duration_t = std::chrono::seconds
   >

   //funzione che utilizza il template e ritorna il tempo impiegato da un momento
   auto since(std::chrono::time_point<clock_t, duration_t> const& start){
       return std::chrono::duration_cast<result_t>(clock_t::now() - start);
   }

   Analysis(TTree *tree=0);
   virtual ~Analysis();
   virtual Int_t    Cut(Long64_t entry);
   virtual Int_t    GetEntry(Long64_t entry);
   virtual Long64_t LoadTree(Long64_t entry);
   virtual void     Init(TTree *tree);
   virtual Bool_t   Notify();
   virtual void     Show(Long64_t entry = -1);

   //Pre dichiarazoni di funzioni aggiunte post generazione del file
   virtual vector<string>     GetNames(string dir_name, bool debug = 0);
   virtual void     process(TTree *tree, string rootfile, string cartella);
   virtual vector<TTree*> InitializeAll();
   virtual void    ProcessAll();
   //virtual void    Cutted_De_TOF_charged();
   virtual void    CreateFolder(string f_path, bool debug = 0);
   virtual void    Clean();
   virtual void    Setter();
   virtual vector<pair<string,string>>  AllNames();

};

#endif

#ifdef Analysis_cxx
//funzione che in genere si usa per aggangiare e inizializzare il TTree
//non utilizzata
Analysis::Analysis(TTree *tree) : fChain(0){

}

Analysis::~Analysis()
{
   if (!fChain) return;
   delete fChain->GetCurrentFile();
}

Int_t Analysis::GetEntry(Long64_t entry)
{
// Read contents of entry.
   if (!fChain) return 0;
   return fChain->GetEntry(entry);
}
Long64_t Analysis::LoadTree(Long64_t entry)
{
// Set the environment to read one entry
   if (!fChain) return -5;
   Long64_t centry = fChain->LoadTree(entry);
   if (centry < 0) return centry;
   if (fChain->GetTreeNumber() != fCurrent) {
      fCurrent = fChain->GetTreeNumber();
      Notify();
   }
   return centry;
}

void Analysis::Init(TTree *tree)
{
   // The Init() function is called when the selector needs to initialize
   // a new tree or chain. Typically here the branch addresses and branch
   // pointers of the tree will be set.
   // It is normally not necessary to make changes to the generated
   // code, but the routine can be extended by the user if needed.
   // Init() will be called many times when running on PROOF
   // (once per file to be processed).

   // Set branch addresses and branch pointers
   if (!tree) return;
   fChain = tree;
   fCurrent = -1;
   fChain->SetMakeClass(1);

   fChain->SetBranchAddress("Idrun", &Idrun, &b_Idrun);
   fChain->SetBranchAddress("Idevt", &Idevt, &b_Idevt);
   fChain->SetBranchAddress("Ipol", &Ipol, &b_Ipol);
   fChain->SetBranchAddress("Itrig", &Itrig, &b_Itrig);
   fChain->SetBranchAddress("Nphys", &Nphys, &b_Nphys);
   fChain->SetBranchAddress("Mplastic", &Mplastic, &b_Mplastic);
   fChain->SetBranchAddress("Iplastic", Iplastic, &b_Iplastic);
   fChain->SetBranchAddress("Eg_tag_pm", Eg_tag_pm, &b_Eg_tag_pm);
   fChain->SetBranchAddress("Ind_bunch_rf", &Ind_bunch_rf, &b_Ind_bunch_rf);
   fChain->SetBranchAddress("Mpm_bad", &Mpm_bad, &b_Mpm_bad);
   fChain->SetBranchAddress("Ipm_bad", Ipm_bad, &b_Ipm_bad);
   fChain->SetBranchAddress("Ncstrip", &Ncstrip, &b_Ncstrip);
   fChain->SetBranchAddress("Mstrip", Mstrip, &b_Mstrip);
   fChain->SetBranchAddress("Xstrip", Xstrip, &b_Xstrip);
   fChain->SetBranchAddress("Eg_tag_strip", Eg_tag_strip, &b_Eg_tag_strip);
   fChain->SetBranchAddress("Iflag_strip", &Iflag_strip, &b_Iflag_strip);
   fChain->SetBranchAddress("Ncstrip_bad", &Ncstrip_bad, &b_Ncstrip_bad);
   fChain->SetBranchAddress("Mstrip_bad", Mstrip_bad, &b_Mstrip_bad);
   fChain->SetBranchAddress("Xstrip_bad", Xstrip_bad, &b_Xstrip_bad);
   fChain->SetBranchAddress("Eg_tag_s_bad", Eg_tag_s_bad, &b_Eg_tag_s_bad);
   fChain->SetBranchAddress("Nbclus", &Nbclus, &b_Nbclus);
   fChain->SetBranchAddress("Mclus", Mclus, &b_Mclus);
   fChain->SetBranchAddress("Eclus", Eclus, &b_Eclus);
   fChain->SetBranchAddress("Tetclus", Tetclus, &b_Tetclus);
   fChain->SetBranchAddress("Phiclus", Phiclus, &b_Phiclus);
   fChain->SetBranchAddress("Eclusc", Eclusc, &b_Eclusc);
   fChain->SetBranchAddress("Tetclusc", Tetclusc, &b_Tetclusc);
   fChain->SetBranchAddress("Phiclusc", Phiclusc, &b_Phiclusc);
   fChain->SetBranchAddress("Ind_bgo", Ind_bgo, &b_Ind_bgo);
   fChain->SetBranchAddress("Emax", Emax, &b_Emax);
   fChain->SetBranchAddress("Sx1", Sx1, &b_Sx1);
   fChain->SetBranchAddress("Sy1", Sy1, &b_Sy1);
   fChain->SetBranchAddress("Sx2", Sx2, &b_Sx2);
   fChain->SetBranchAddress("Sy2", Sy2, &b_Sy2);
   fChain->SetBranchAddress("Ifl", Ifl, &b_Ifl);
   fChain->SetBranchAddress("Nass_2", &Nass_2, &b_Nass_2);
   fChain->SetBranchAddress("Iass_2", Iass_2, &b_Iass_2);
   fChain->SetBranchAddress("Nass_3", &Nass_3, &b_Nass_3);
   fChain->SetBranchAddress("Iass_3", Iass_3, &b_Iass_3);
   fChain->SetBranchAddress("Itipo_track", Itipo_track, &b_Itipo_track);
   fChain->SetBranchAddress("I_bar_track", I_bar_track, &b_I_bar_track);
   fChain->SetBranchAddress("Dedx_track", Dedx_track, &b_Dedx_track);
   fChain->SetBranchAddress("T_bar_track", T_bar_track, &b_T_bar_track);
   fChain->SetBranchAddress("Ind_bar_track", Ind_bar_track, &b_Ind_bar_track);
   fChain->SetBranchAddress("Phi_bar_track", Phi_bar_track, &b_Phi_bar_track);
   fChain->SetBranchAddress("Eclusc_track", Eclusc_track, &b_Eclusc_track);
   fChain->SetBranchAddress("Thet_bgo_track", Thet_bgo_track, &b_Thet_bgo_track);
   fChain->SetBranchAddress("Phi_bgo_track", Phi_bgo_track, &b_Phi_bgo_track);
   fChain->SetBranchAddress("Thet_cyl_track", Thet_cyl_track, &b_Thet_cyl_track);
   fChain->SetBranchAddress("Phi_cyl_track", Phi_cyl_track, &b_Phi_cyl_track);
   fChain->SetBranchAddress("Thet_centr_track", Thet_centr_track, &b_Thet_centr_track);
   fChain->SetBranchAddress("Phi_centr_track", Phi_centr_track, &b_Phi_centr_track);
   fChain->SetBranchAddress("Nbclus_sp", &Nbclus_sp, &b_Nbclus_sp);
   fChain->SetBranchAddress("Mclus_sp", Mclus_sp, &b_Mclus_sp);
   fChain->SetBranchAddress("Eclus_sp", Eclus_sp, &b_Eclus_sp);
   fChain->SetBranchAddress("Tetclus_sp", Tetclus_sp, &b_Tetclus_sp);
   fChain->SetBranchAddress("Phiclus_sp", Phiclus_sp, &b_Phiclus_sp);
   fChain->SetBranchAddress("Eclusc_sp", Eclusc_sp, &b_Eclusc_sp);
   fChain->SetBranchAddress("Tetclusc_sp", Tetclusc_sp, &b_Tetclusc_sp);
   fChain->SetBranchAddress("Phiclusc_sp", Phiclusc_sp, &b_Phiclusc_sp);
   fChain->SetBranchAddress("Nbar", &Nbar, &b_Nbar);
   fChain->SetBranchAddress("Ibar", Ibar, &b_Ibar);
   fChain->SetBranchAddress("Ebar", Ebar, &b_Ebar);
   fChain->SetBranchAddress("Timbar", Timbar, &b_Timbar);
   fChain->SetBranchAddress("Ind_bar", Ind_bar, &b_Ind_bar);
   fChain->SetBranchAddress("Nbarc", &Nbarc, &b_Nbarc);
   fChain->SetBranchAddress("Mhtbgo", &Mhtbgo, &b_Mhtbgo);
   fChain->SetBranchAddress("Ihtbgo", Ihtbgo, &b_Ihtbgo);
   fChain->SetBranchAddress("Htbgo", Htbgo, &b_Htbgo);
   fChain->SetBranchAddress("Ttot", &Ttot, &b_Ttot);
   fChain->SetBranchAddress("Lpm_b_b", &Lpm_b_b, &b_Lpm_b_b);
   fChain->SetBranchAddress("Lanabar", &Lanabar, &b_Lanabar);
   fChain->SetBranchAddress("Lanabgo", &Lanabgo, &b_Lanabgo);
   fChain->SetBranchAddress("Lanamatch", &Lanamatch, &b_Lanamatch);
   fChain->SetBranchAddress("Lpm0", &Lpm0, &b_Lpm0);
   fChain->SetBranchAddress("Ntra", &Ntra, &b_Ntra);
   fChain->SetBranchAddress("A1", A1, &b_A1);
   fChain->SetBranchAddress("A2", A2, &b_A2);
   fChain->SetBranchAddress("A3", A3, &b_A3);
   fChain->SetBranchAddress("B1", B1, &b_B1);
   fChain->SetBranchAddress("B2", B2, &b_B2);
   fChain->SetBranchAddress("B3", B3, &b_B3);
   fChain->SetBranchAddress("De", De, &b_De);
   fChain->SetBranchAddress("Tf", Tf, &b_Tf);
   fChain->SetBranchAddress("Icol1", Icol1, &b_Icol1);
   fChain->SetBranchAddress("Icol2", Icol2, &b_Icol2);
   fChain->SetBranchAddress("Cl1", Cl1, &b_Cl1);
   fChain->SetBranchAddress("Cltot1", &Cltot1, &b_Cltot1);
   fChain->SetBranchAddress("Lm_1", &Lm_1, &b_Lm_1);
   fChain->SetBranchAddress("Ip1_cor", Ip1_cor, &b_Ip1_cor);
   fChain->SetBranchAddress("Ene_l", Ene_l, &b_Ene_l);
   fChain->SetBranchAddress("Ene_r", Ene_r, &b_Ene_r);
   fChain->SetBranchAddress("Tof_l", Tof_l, &b_Tof_l);
   fChain->SetBranchAddress("Tof_r", Tof_r, &b_Tof_r);
   fChain->SetBranchAddress("Delta_tof_h", Delta_tof_h, &b_Delta_tof_h);
   fChain->SetBranchAddress("Amean_tof_h", Amean_tof_h, &b_Amean_tof_h);
   fChain->SetBranchAddress("T_lr", T_lr, &b_T_lr);
   fChain->SetBranchAddress("A_tof1", A_tof1, &b_A_tof1);
   fChain->SetBranchAddress("A_de1", A_de1, &b_A_de1);
   fChain->SetBranchAddress("X_w1", X_w1, &b_X_w1);
   fChain->SetBranchAddress("Y_w1", Y_w1, &b_Y_w1);
   fChain->SetBranchAddress("Iass_w1", Iass_w1, &b_Iass_w1);
   fChain->SetBranchAddress("Lm_2", &Lm_2, &b_Lm_2);
   fChain->SetBranchAddress("Ip2_cor", Ip2_cor, &b_Ip2_cor);
   fChain->SetBranchAddress("Ene_u", Ene_u, &b_Ene_u);
   fChain->SetBranchAddress("Ene_d", Ene_d, &b_Ene_d);
   fChain->SetBranchAddress("Tof_u", Tof_u, &b_Tof_u);
   fChain->SetBranchAddress("Tof_d", Tof_d, &b_Tof_d);
   fChain->SetBranchAddress("Delta_tof_v", Delta_tof_v, &b_Delta_tof_v);
   fChain->SetBranchAddress("Amean_tof_v", Amean_tof_v, &b_Amean_tof_v);
   fChain->SetBranchAddress("T_ud", T_ud, &b_T_ud);
   fChain->SetBranchAddress("A_tof2", A_tof2, &b_A_tof2);
   fChain->SetBranchAddress("A_de2", A_de2, &b_A_de2);
   fChain->SetBranchAddress("X_w2", X_w2, &b_X_w2);
   fChain->SetBranchAddress("Y_w2", Y_w2, &b_Y_w2);
   fChain->SetBranchAddress("Iass_w2", Iass_w2, &b_Iass_w2);
   fChain->SetBranchAddress("M_wal", &M_wal, &b_M_wal);
   fChain->SetBranchAddress("Wal_par", Wal_par, &b_Wal_par);
   fChain->SetBranchAddress("Ind_par", Ind_par, &b_Ind_par);
   fChain->SetBranchAddress("Theta_w", Theta_w, &b_Theta_w);
   fChain->SetBranchAddress("Phi_w", Phi_w, &b_Phi_w);
   fChain->SetBranchAddress("Ind_wal", Ind_wal, &b_Ind_wal);
   fChain->SetBranchAddress("Iass_track", Iass_track, &b_Iass_track);
   fChain->SetBranchAddress("Nppln2", &Nppln2, &b_Nppln2);
   fChain->SetBranchAddress("U_pc", U_pc, &b_U_pc);
   fChain->SetBranchAddress("V_pc", V_pc, &b_V_pc);
   fChain->SetBranchAddress("X_pc", X_pc, &b_X_pc);
   fChain->SetBranchAddress("Y_pc", Y_pc, &b_Y_pc);
   fChain->SetBranchAddress("N_traf", &N_traf, &b_N_traf);
   fChain->SetBranchAddress("Ind_traf", Ind_traf, &b_Ind_traf);
   fChain->SetBranchAddress("Iass_trf", Iass_trf, &b_Iass_trf);
   fChain->SetBranchAddress("Iforw_c", &Iforw_c, &b_Iforw_c);
   fChain->SetBranchAddress("Iforw_n", &Iforw_n, &b_Iforw_n);
   fChain->SetBranchAddress("Nparf", &Nparf, &b_Nparf);
   fChain->SetBranchAddress("Nparf_c", &Nparf_c, &b_Nparf_c);
   fChain->SetBranchAddress("Nparf_n", &Nparf_n, &b_Nparf_n);
   fChain->SetBranchAddress("Nparf_strange", &Nparf_strange, &b_Nparf_strange);
   fChain->SetBranchAddress("Cos_trf", Cos_trf, &b_Cos_trf);
   fChain->SetBranchAddress("Theta_trf", Theta_trf, &b_Theta_trf);
   fChain->SetBranchAddress("Phi_trf", Phi_trf, &b_Phi_trf);
   fChain->SetBranchAddress("Tof_trf", Tof_trf, &b_Tof_trf);
   fChain->SetBranchAddress("De_trf", De_trf, &b_De_trf);
   fChain->SetBranchAddress("Index_trf", Index_trf, &b_Index_trf);
   fChain->SetBranchAddress("Info_wal", Info_wal, &b_Info_wal);
   fChain->SetBranchAddress("Nshow", &Nshow, &b_Nshow);
   fChain->SetBranchAddress("Eshow", Eshow, &b_Eshow);
   fChain->SetBranchAddress("Tshow", Tshow, &b_Tshow);
   fChain->SetBranchAddress("Yshow", Yshow, &b_Yshow);
   fChain->SetBranchAddress("Xshow", Xshow, &b_Xshow);
   fChain->SetBranchAddress("Tetshow", Tetshow, &b_Tetshow);
   fChain->SetBranchAddress("Phishow", Phishow, &b_Phishow);
   fChain->SetBranchAddress("Tshpc", Tshpc, &b_Tshpc);
   fChain->SetBranchAddress("Pshpc", Pshpc, &b_Pshpc);
   fChain->SetBranchAddress("Typeshow", Typeshow, &b_Typeshow);
   fChain->SetBranchAddress("N_ur", &N_ur, &b_N_ur);
   fChain->SetBranchAddress("Nsh_ur", Nsh_ur, &b_Nsh_ur);
   fChain->SetBranchAddress("Esh_ur", Esh_ur, &b_Esh_ur);
   fChain->SetBranchAddress("Ts_ur", Ts_ur, &b_Ts_ur);
   fChain->SetBranchAddress("Nb_traces_cyl", &Nb_traces_cyl, &b_Nb_traces_cyl);
   fChain->SetBranchAddress("Dz_trace_int", Dz_trace_int, &b_Dz_trace_int);
   fChain->SetBranchAddress("Dz_trace_ext", Dz_trace_ext, &b_Dz_trace_ext);
   fChain->SetBranchAddress("X_trace_int", X_trace_int, &b_X_trace_int);
   fChain->SetBranchAddress("Y_trace_int", Y_trace_int, &b_Y_trace_int);
   fChain->SetBranchAddress("Z_trace_int", Z_trace_int, &b_Z_trace_int);
   fChain->SetBranchAddress("X_trace_ext", X_trace_ext, &b_X_trace_ext);
   fChain->SetBranchAddress("Y_trace_ext", Y_trace_ext, &b_Y_trace_ext);
   fChain->SetBranchAddress("Z_trace_ext", Z_trace_ext, &b_Z_trace_ext);
   fChain->SetBranchAddress("Dphi_trace_cyl", Dphi_trace_cyl, &b_Dphi_trace_cyl);
   fChain->SetBranchAddress("Teta_trace_cyl", Teta_trace_cyl, &b_Teta_trace_cyl);
   fChain->SetBranchAddress("Phi_trace_cyl", Phi_trace_cyl, &b_Phi_trace_cyl);
   fChain->SetBranchAddress("Z_trace_cyl", Z_trace_cyl, &b_Z_trace_cyl);
   fChain->SetBranchAddress("Status_traces_cyl", &Status_traces_cyl, &b_Status_traces_cyl);
   fChain->SetBranchAddress("Lctdb", &Lctdb, &b_Lctdb);
   fChain->SetBranchAddress("Ictdb", Ictdb, &b_Ictdb);
   fChain->SetBranchAddress("Ectdb", Ectdb, &b_Ectdb);
   fChain->SetBranchAddress("Tctdb", Tctdb, &b_Tctdb);
   fChain->SetBranchAddress("Lctdf", &Lctdf, &b_Lctdf);
   fChain->SetBranchAddress("Ictdf", Ictdf, &b_Ictdf);
   fChain->SetBranchAddress("Ectdf", Ectdf, &b_Ectdf);
   fChain->SetBranchAddress("Tctdf", Tctdf, &b_Tctdf);
   Notify();
}

Bool_t Analysis::Notify()
{
   // The Notify() function is called when a new file is opened. This
   // can be either for a new TTree in a TChain or when when a new TTree
   // is started when using PROOF. It is normally not necessary to make changes
   // to the generated code, but the routine can be extended by the
   // user if needed. The return value is currently not used.

   return kTRUE;
}

void Analysis::Show(Long64_t entry)
{
// Print contents of entry.
// If entry is not specified, print current entry
   if (!fChain) return;
   fChain->Show(entry);
}
Int_t Analysis::Cut(Long64_t entry)
{
// This function may be called from Loop.
// returns  1 if entry is accepted.
// returns -1 otherwise.
   return 1;
}
#endif // #ifdef Analysis_cxx
