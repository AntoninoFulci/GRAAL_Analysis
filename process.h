///////////////////////////////////////////////////
// Header file contenente l'argoritmo di processing
// l'algoritmo prende un albero e lo cerca di
// analizzare
///////////////////////////////////////////////////
#include "CutEtapNeu.C"
#include "CutEtapPro.C"
#include "Cut1deu.C"
#include "Cut1deu_4ph.C"
#include "Cut1deu_2ph.C"
#include "Cut1pro_4ph.C"
#include "Cut1fch_4ph.C"
#include "Cuts.C"

void Analysis::process(TTree *alb, string root_file, string cartella){

  //Funzione di inizializzazione dell'albero passato
  Analysis::Init(alb);

  //Inizio algoritmo
  double RMP    = 0.9382720813;
  double RMN    = 0.939485;
  double RMD = 1.877;
  double CLIGHT = 29979245800.; //! cm/sec
  double DIST_WALL;
  double percent = 10.0;

  TCutG *ProtonCentrCut   = myProtonCentrCut(cartella);
  TCutG *PionCentrCut     = myPionCentrCut(cartella);
  TCutG *ProtonForwCut    = myProtonForwCut(cartella);
  TCutG *PionForwCut      = myPionForwCut(cartella);
  TCutG *DeuForwCut       = myDeuForwCut(cartella);


  //TF1 *FitDeu_centr = myFit_Deu_centr(cartella); // identifichiamo i deuteroni al centro con gli eventi che "stanno" sopra un fit
/*
TF1 *FitDeuCentr_2005_d2 = new TF1("FitDeuCentr_2005_d2","[0]+[1]*x+[2]*pow(x,2)+[3]*pow(x,3)+[4]*pow(x,4)+[5]*pow(x,5)+[6]*pow(x,6)+[7]*pow(x,7)+[8]*pow(x,8)+[9]*pow(x,9)+[10]*pow(x,10)",0.,0.28);
FitDeuCentr_2005_d2->SetParameters(36.3101,-542.913,3588.08,-9161.96,1087.51,18776.7,15990.1,-20040.1,-74556.9,-97890.8,-8750.13);
*/


  string str1 = "dEdx_Er_" + cartella;

  string str2 = "ddxtof_f_" + cartella;

  string str3 = "ddxtof_fow_" + cartella;

  string str4 = "Theta_trf_fch_" + cartella;
  string str5 = "Phi_trf_fch_" + cartella;
  string str6 = "Theta_trf_fn_" + cartella;
  string str7 = "Phi_trf_fn_" + cartella;
  string str8 = "N_show_" + cartella;
  string str9 = "E_show_"+ cartella;
  string str10 = "Iass_trf_" + cartella;
  string str11 = "ind_trf_" + cartella;
  string str12 = "../Forw_tracks_"+cartella;
  string str13 = "BeamE_"+cartella;
  string str14 = "Tof_vs_Dedx_vs_idrun_"+cartella;
  string str15 = "dEdx_Er_Ind_bar_"+cartella;
  string str16 = ".png";
  string str17 = ".pdf";
  string str18 = "soloProdirty";
  string str19 = "soloPiondirty";
  string str20 = str1 + str18;
  string str21 = str1 + str19;
  string str22 = str3 + str18;
  string str23 = str3 + str19;
  string str24 = "soloProclean";
  string str25 = "soloPionclean";
  string str26 = str1 + str24;
  string str27 = str1 + str25;
  string str28 = str3 + str24;
  string str29 = str3 + str25;

  printcuts("grafici_sim_prean_EtapN.root");
  TCutG *cutg1 = CutEgThetaN("grafici_sim_prean_EtapN.root");
  TCutG *cutg2 = CutEgEn("grafici_sim_prean_EtapN.root");

  // file di testo che salva i valori calcolato dell'incertezza sul momento delle particlele in avanti dalle misure di tempo di volo
  ofstream scr1("incertezza_Pdeu.txt");


  TH2D *protondxE         = new TH2D(str1.c_str(),str1.c_str(),100,0,1.2,100,0,20); // distribuzione perdita di energia vs energia nel BGO di tutte le tracce cariche(MWC-Bar-BGO) al centro
  TH2D *dEdxErsoloProdirty  = new TH2D(str20.c_str(),str20.c_str(),100,0,1.2,100,0,20); // distribuzione perdita di energia vs energia nel BGO solo protoni dopo che questi sono stati identificati con il taglio sul grafico De/dx vs Er.
  TH2D *dEdxErsoloPiondirty  = new TH2D(str21.c_str(),str21.c_str(),100,0,1.2,100,0,20); // distribuzione perdita di energia vs energia nel BGO solo pioni dopo che questi sono stati identificati con il taglio sul grafico De/dx vs Er.
  TH2D *ddxtof_f          = new TH2D(str2.c_str(),str2.c_str(),100,0.,0.,100,-250.,250.); // distribuzione perdita di energia vs tempo di volo per particelle neutre emesse in avanti.
  TH2D *ddxtof_fow        = new TH2D(str3.c_str(),str3.c_str(),50,0.,0.,50,0.,2000.); // distribuzione perdita di energia vs tempo di volo per particelle cariche emesse in avanti.
  TH2D *ddxtof_fow_Pro = new TH2D(str22.c_str(),str22.c_str(),50,0.,0.,50,0.,2000.); // distirbuzione perdita di energia vs tempo di volo che identifica i protoni
  TH2D *ddxtof_fow_Pion = new TH2D(str23.c_str(),str23.c_str(),50,0.,0.,50,0.,2000.); // distirbuzione perdita di energia vs tempo di volo che identifica i pioni

  string dedxerproeta_ = str26 + "EtaPro";
  //string dedxerpioneta_ = str21 + "Eta";
  string dedxerpionnpip = str27 + "npip";
  string ddxtofpronpip = str28 + "npip";
  string ddxtofpionnpip = str29 + "npip";

  // istogrammi De/dx vs Er che identificano i protoni tra le tracce centrali sotto la condizione di avere almeno due fotoni centrali e un'energia del gamma maggiore della soglia(condizioni preliminari per il canale gamma p eta p)
  TH2D *dEdxErsoloPro_EtaPro = new TH2D(dedxerproeta_.c_str(),dedxerproeta_.c_str(),100,0.,1.2,100,0,20);
  TH2D *dEdxErsoloPion_pipn = new TH2D(dedxerpionnpip.c_str(),dedxerpionnpip.c_str(),100,0.,1.2,100,0,20);
  // istogrammi De vs Tof che identificano i pioni carichi tra le tracce in avanti
  TH2D *ddxtofsoloPro_pipn = new TH2D(ddxtofpronpip.c_str(),ddxtofpronpip.c_str(),100,0.,0.,100,0.,0.);
  TH2D *ddxtofsoloPion_pipn = new TH2D(ddxtofpionnpip.c_str(),ddxtofpionnpip.c_str(),100,0.,0.,100,0.,0.);

  TH1D *N_show_ = new TH1D(str8.c_str(),"",100,0.,0.); // distribuzione del numero di colpi nel Russian Wall
  TH1D *E_show_ = new TH1D(str9.c_str(),"",20,0.,0.2); // distribuzione dell'energia depositata nel Russian Wall
  TH1D *Iass_trf_ = new TH1D(str10.c_str(),"",10,0.,10.); // distribuzione dell'indice che identifica il tipo di traccia in avanti
  TH1D *ind_trf = new TH1D(str11.c_str(),"",10,0.,10); // distribuzione dell'indice contenente l'informazione sull'associazione dei rivelatori in avanti
  TH1D *Theta_trf_fch = new TH1D(str4.c_str(),"",170,0.,0.); // distribuzione angolo theta delle tracce "cariche" emesse in avanti
  TH1D *Phi_trf_fch = new TH1D(str5.c_str(),"",350,0.,0.); // distribuzione angolo phi delle tracce "cariche" emesse in avanti
  TH1D *Theta_trf_fn = new TH1D(str6.c_str(),"",60,0.,0.); // distribuzione angolo theta delle tracce "cariche" emesse in avanti
  TH1D *Phi_trf_fn = new TH1D(str7.c_str(),"",72,0.,0.); // distribuzione angolo phi delle tracce "cariche" emesse in avanti
  TH1D *BeamE = new TH1D(str13.c_str(),"",128,0.55,1.600);

  TH3D *protondxE_Ind_bar = new TH3D(str15.c_str(),"",32,0.5,32.5,200,0.,0.8,40,0.,40.); // grafico dE/dx vs Er vs Indice della barra del barrel
  TH3D *Dedx_Tof_idrun = new TH3D(str14.c_str(),"",100,0.,0.,100,0.,0.,300,0.,0.);

  TFile *dati = new TFile(root_file.c_str(),"recreate");
  TTree *tree = new TTree("h80","Graal data Analysis");

  //string Name_f = "../Dedx_vs_T.O.F.root";

  int idrun, idevt, ipol;

  vector<TLorentzVector> cphoton;
  vector<TLorentzVector> proton;
  // vector<TLorentzVector> cproton;
  vector<pair<double,double> > pionangles;
  vector<pair<double,double> > fphotonangles;
  // vector<TLorentzVector> fproton;
  vector<TLorentzVector> fneutron;
  vector<TLorentzVector> fDeuteron; // creiamo un vettore che contiene tutte le particelle promosse a "deuteroni in avanti" in ogni evento(ma lo facciamo solo se sulle analisi su deuterio)
  //vector<TLorentzVector> cDeuteron;  // lo stesso facciamo con i deuteroni al centro
  vector<TLorentzVector> ccharged; // ipotesi di un carico emesso ad angoli centrali che non sia un pione carico(da utilizzare in futuro..)
  vector<TLorentzVector> fcharged; // ipotesi di un carico emesso ad angoli in avanti che non sia un pione
  vector<pair<double,double> > fproangles;
  vector<pair<double,double> > fdeuangles;
  vector<double> Tof_fpro;
  vector<double> Tof_fdeu;
  vector<double> Tof_fch;
  int fch;

  // vettore delle molteplicità dei clusters
  vector<int> MClus;

  TLorentzVector beam;

  tree->Branch("beam",    "TLorentzVector", &beam);
  tree->Branch("idrun",   &idrun, "idrun/I");   // numero del run
  tree->Branch("idevt",   &idevt, "idevt/I");   // numero dati dell'evento
  tree->Branch("ipol",    &ipol,  "ipol/I");    // polarizzazione del fascio: 0 verticale, 1 orizzontale, 2 bremsstrahlung
  tree->Branch("cphoton", &cphoton);
  // tree->Branch("cproton", &cproton);
  //tree->Branch("proton",  &proton);
  // tree->Branch("fproton", &fproton);
  //tree->Branch("fneutron",&fneutron);
  //tree->Branch("pionangles",    &pionangles);
  //tree->Branch("fphotonangles", &fphotonangles);
  //tree->Branch("fDeuteron", &fDeuteron); // questo cre
  tree->Branch("fproangles",&fproangles);
  tree->Branch("fdeuangles",&fdeuangles);
  //tree->Branch("Tof_fpro",&Tof_fpro);
  //tree->Branch("Tof_fdeu",&Tof_fdeu);
  tree->Branch("Tof_fch",&Tof_fch); // branch che raccoglie i valori del "tempo di volo" dei carichi in avanti ad ogni evento
  tree->Branch("fch",&fch); // branch che raccoglie  il numero di particelle cariche emesse in avanti ad ogni evento
  //tree->Branch("MClus",&MClus);

  // taglio energia gamma vs angolo theta del neutrone per identificare gli eventi del canale di fotoproduzione di etaprimo su neutrone
  TCutG *CutEgThN = new TCutG("CutEgThN",22);
  CutEgThN->SetVarX("beam energy(GeV)");
  CutEgThN->SetVarY("neutron theta(degree)");
  CutEgThN->SetTitle("Graph");
  CutEgThN->SetFillStyle(1000);
  CutEgThN->SetPoint(0,1.43954,0.158279);
  CutEgThN->SetPoint(1,1.44292,2.79627);
  CutEgThN->SetPoint(2,1.44631,4.16599);
  CutEgThN->SetPoint(3,1.4497,5.28206);
  CutEgThN->SetPoint(4,1.45681,6.80398);
  CutEgThN->SetPoint(5,1.46223,8.07224);
  CutEgThN->SetPoint(6,1.47848,10.4566);
  CutEgThN->SetPoint(7,1.48864,11.7756);
  CutEgThN->SetPoint(8,1.50354,13.6526);
  CutEgThN->SetPoint(9,1.51065,14.6165);
  CutEgThN->SetPoint(10,1.52555,15.8847);
  CutEgThN->SetPoint(11,1.5479,17.6096);
  CutEgThN->SetPoint(12,1.56483,18.9286);
  CutEgThN->SetPoint(13,1.60513,21.668);
  CutEgThN->SetPoint(14,1.60377,10);
  CutEgThN->SetPoint(15,1.60547,-0.298295);
  CutEgThN->SetPoint(16,1.59226,-0.0446428);
  CutEgThN->SetPoint(17,1.56111,-0.146104);
  CutEgThN->SetPoint(18,1.52758,-0.349026);
  CutEgThN->SetPoint(19,1.48932,-0.146104);
  CutEgThN->SetPoint(20,1.47848,0.0568182);
  CutEgThN->SetPoint(21,1.43954,0.158279);

   /*
   // taglio energia de fascio vs angolo theta del protone per selezionare gli eventi del canale di fotoproduzione di etaprimo su protone sopra la soglia
   TCutG *cutg = new TCutG("cutg",22);
   cutg->SetVarX("Energy gamma(GeV)");
   cutg->SetVarY("Theta proton(degree)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,1.44258,-0.171875);
   cutg->SetPoint(1,1.44196,2.69271);
   cutg->SetPoint(2,1.44917,5.46181);
   cutg->SetPoint(3,1.45606,7.2283);
   cutg->SetPoint(4,1.46515,8.99479);
   cutg->SetPoint(5,1.47988,11.0477);
   cutg->SetPoint(6,1.49586,13.1007);
   cutg->SetPoint(7,1.51529,15.3924);
   cutg->SetPoint(8,1.54256,17.5885);
   cutg->SetPoint(9,1.55979,19.0686);
   cutg->SetPoint(10,1.58048,20.3576);
   cutg->SetPoint(11,1.59928,21.3602);
   cutg->SetPoint(12,1.60336,21.0738);
   cutg->SetPoint(13,1.60242,16.6337);
   cutg->SetPoint(14,1.60304,12.3845);
   cutg->SetPoint(15,1.60304,7.41927);
   cutg->SetPoint(16,1.60398,2.40625);
   cutg->SetPoint(17,1.60367,-0.028646);
   cutg->SetPoint(18,1.52563,0.0668401);
   cutg->SetPoint(19,1.4523,0.0190971);
   cutg->SetPoint(20,1.44196,-0.0763891);
   cutg->SetPoint(21,1.44258,-0.171875);

   // taglio Energia gamma vs angolo theta del neutrone ristretto ad un valore leggermente più basso del valore massimo dello spettro del gamma
   TCutG *CutThetaNEg_test = new TCutG("CutThetaNEg_test",22);
   CutThetaNEg_test->SetVarX("beam energy(GeV)");
   CutThetaNEg_test->SetVarY("neutron theta(degree)");
   CutThetaNEg_test->SetTitle("Graph");
   CutThetaNEg_test->SetFillStyle(1000);
   CutThetaNEg_test->SetPoint(0,1.44492,-0.0830976);
   CutThetaNEg_test->SetPoint(1,1.446,1.79649);
   CutThetaNEg_test->SetPoint(2,1.44707,3.03306);
   CutThetaNEg_test->SetPoint(3,1.45065,4.46748);
   CutThetaNEg_test->SetPoint(4,1.45744,6.49546);
   CutThetaNEg_test->SetPoint(5,1.46209,7.78149);
   CutThetaNEg_test->SetPoint(6,1.4789,10.1062);
   CutThetaNEg_test->SetPoint(7,1.48928,11.4417);
   CutThetaNEg_test->SetPoint(8,1.50287,13.3708);
   CutThetaNEg_test->SetPoint(9,1.51109,14.3106);
   CutThetaNEg_test->SetPoint(10,1.52612,15.5472);
   CutThetaNEg_test->SetPoint(11,1.54829,17.2784);
   CutThetaNEg_test->SetPoint(12,1.56546,18.6138);
   CutThetaNEg_test->SetPoint(13,1.59193,18.6138);
   CutThetaNEg_test->SetPoint(14,1.59121,13.1235);
   CutThetaNEg_test->SetPoint(15,1.59121,7.13847);
   CutThetaNEg_test->SetPoint(16,1.59193,0.0652909);
   CutThetaNEg_test->SetPoint(17,1.55938,0.0652909);
   CutThetaNEg_test->SetPoint(18,1.5254,0.0158281);
   CutThetaNEg_test->SetPoint(19,1.4832,0.0158281);
   CutThetaNEg_test->SetPoint(20,1.44492,-0.0336348);
   CutThetaNEg_test->SetPoint(21,1.44492,-0.0830976);


   // taglio energia fascio vs angolo theta del protone per il canale di fotoproduzione di etaprimo su protone, allargato ad un bin di energia sotto la soglia
   TCutG *cutg3 = new TCutG("cutg3",21);
   cutg3->SetVarX("beam energy(GeV)");
   cutg3->SetVarY("Proton Theta(°)");
   cutg3->SetTitle("Graph");
   cutg3->SetFillStyle(1000);
   cutg3->SetPoint(0,1.43309,-0.152027);
   cutg3->SetPoint(1,1.43309,1.97635);
   cutg3->SetPoint(2,1.43517,4.61149);
   cutg3->SetPoint(3,1.44378,7.5);
   cutg3->SetPoint(4,1.45417,9.72973);
   cutg3->SetPoint(5,1.46545,11.9088);
   cutg3->SetPoint(6,1.48118,14.3919);
   cutg3->SetPoint(7,1.49899,16.1655);
   cutg3->SetPoint(8,1.52036,18.0405);
   cutg3->SetPoint(9,1.54233,19.7635);
   cutg3->SetPoint(10,1.56697,21.2331);
   cutg3->SetPoint(11,1.58359,22.1959);
   cutg3->SetPoint(12,1.60051,22.5);
   cutg3->SetPoint(13,1.60081,20.3209);
   cutg3->SetPoint(14,1.6017,8.46284);
   cutg3->SetPoint(15,1.6011,0.050676);
   cutg3->SetPoint(16,1.5358,2.8657e-07);
   cutg3->SetPoint(17,1.47405,0.101352);
   cutg3->SetPoint(18,1.4325,-0.0506754);
   cutg3->SetPoint(19,1.48296,0.101352);
   cutg3->SetPoint(20,1.43309,-0.152027);


   // taglio energia fascio vs angolo theta del neutrone per il canale di fotoproduzione di etaprimo su neutrone, allargato ad un bin di energia sotto la soglia
   TCutG *cutg4 = new TCutG("cutg4",20);
   cutg4->SetVarX("beam energy(GeV)");
   cutg4->SetVarY("Neutron theta(°)");
   cutg4->SetTitle("Graph");
   cutg4->SetFillStyle(1000);
   cutg4->SetPoint(0,1.56128,18.08);
   cutg4->SetPoint(1,1.561,14.3895);
   cutg4->SetPoint(2,1.56042,9.60866);
   cutg4->SetPoint(3,1.56014,4.74394);
   cutg4->SetPoint(4,1.56014,-0.0788419);
   cutg4->SetPoint(5,1.53607,-0.0369047);
   cutg4->SetPoint(6,1.49567,-0.0788419);
   cutg4->SetPoint(7,1.46673,0.0469697);
   cutg4->SetPoint(8,1.44352,-0.0788419);
   cutg4->SetPoint(9,1.43206,-0.0788419);
   cutg4->SetPoint(10,1.4332,1.55671);
   cutg4->SetPoint(11,1.4355,3.69551);
   cutg4->SetPoint(12,1.44323,5.91818);
   cutg4->SetPoint(13,1.44925,7.38598);
   cutg4->SetPoint(14,1.46157,9.48285);
   cutg4->SetPoint(15,1.47504,12.1668);
   cutg4->SetPoint(16,1.51687,16.6122);
   cutg4->SetPoint(17,1.54209,17.9961);
   cutg4->SetPoint(18,1.56128,18.2058);
   cutg4->SetPoint(19,1.56128,18.08);
   */

   ofstream scrivimi("beamE.txt");

   ofstream scrivimi2("MClu.txt");

   int nphotons;
   int nneutrons;
   int nccharged;


  if (fChain == 0) return;
  Long64_t nentries = fChain->GetEntriesFast();
  Long64_t nbytes = 0, nb = 0;

  for (Long64_t jentry=0; jentry<nentries; jentry++){
    Long64_t ientry = LoadTree(jentry);
    if (ientry < 0) break;
    nb = fChain->GetEntry(jentry);   nbytes += nb;
    fproangles.clear();
    fdeuangles.clear();
    cphoton.clear();
    proton.clear();
    fneutron.clear();
    pionangles.clear();
    fphotonangles.clear();
    fDeuteron.clear();
    Tof_fch.clear();
    Tof_fpro.clear();
    Tof_fdeu.clear();
    //MClus.clear();
    nphotons=0;
    nneutrons=0;
    nccharged=0;

    fch=0;

    // if (Cut(ientry) < 0) continue;
    idrun = Idrun;
    idevt = Idevt;
    ipol  = int(Ipol);


    int fpro = 0;
    int cpro = 0;

    beam.SetPxPyPzE(0.,0.,Eg_tag_strip[0],Eg_tag_strip[0]);
    BeamE->Fill(beam.E());
    //fa un ciclo su tutte le traccie rivelate al centro
    for(int i=0; i<Nass_3; i++){
      //cout<<Itipo_track[i]<<endl;
      if(Itipo_track[i]==11){ // le tracce che sono associate al codice 002(solo BGO) rappresentano eventi centrali neutri caratterizzati da una deposizione di energia di cluster minore 15 MeV(soglia software) ma comunque maggiore di 2 MeV su singolo cristallo(soglia hardware): questi eventi sono associati a fotoni di bassa energia per cui sono stati rigettati nell'analisi
        TLorentzVector CandidatePhoton;
        CandidatePhoton.SetPxPyPzE(Eclusc_track[i]*sin(Thet_centr_track[i]/180.*M_PI)*cos(Phi_centr_track[i]/180.*M_PI),Eclusc_track[i]*sin(Thet_centr_track[i]/180.*M_PI)*sin(Phi_centr_track[i]/180.*M_PI),Eclusc_track[i]*cos(Thet_centr_track[i]/180.*M_PI),Eclusc_track[i]);
        cphoton.push_back(CandidatePhoton);
        //int mclus = atoi(&Mclus[i]);
        //MClus.push_back(mclus);
        nphotons++;
        nneutrons++;
      }
      if(Itipo_track[i]==13 || Itipo_track[i]==14){ //le tracce classificate come Itipo_track=24 che sono eventi carichi associati al codice 112(camere a filo-barrel-BGO) con segnale sopra soglia sul barrel e tempo di volo all'interno della finestra temporale, ma associati ad una deposizione di energia nel cluster del calorimetro BGO minore di 15 MeV
        protondxE->Fill(Eclusc_track[i], Dedx_track[i]);
        int I_bar_track_ = static_cast<int>(I_bar_track[i]);
        protondxE_Ind_bar->Fill(I_bar_track_,Eclusc_track[i], Dedx_track[i]);
        TLorentzVector CandidateProton;
        if(ProtonCentrCut->IsInside(Eclusc_track[i], Dedx_track[i])){
          dEdxErsoloProdirty->Fill(Eclusc_track[i], Dedx_track[i]);
          //   double Etotpro = Eclusc_track[i] + Dedx_track[i]/(2*sin(Thet_centr_track[i]/180.*M_PI)*1000.) + RMP;
          double Etotpro = Eclusc_track[i] + RMP;
          TLorentzVector CandidateProton;
          double Ppro = sqrt(Etotpro*Etotpro-RMP*RMP);
          CandidateProton.SetPxPyPzE(Ppro*sin(Thet_centr_track[i]/180.*M_PI)*cos(Phi_centr_track[i]/180.*M_PI), Ppro*sin(Thet_centr_track[i]/180.*M_PI)*sin(Phi_centr_track[i]/180.*M_PI), Ppro*cos(Thet_centr_track[i]/180.*M_PI),Etotpro);
          proton.push_back(CandidateProton);
          ccharged.push_back(CandidateProton);
          cpro++;
          /*
          if(nphotons>=2 && Eg_tag_strip[0]>=1.018){
            dEdxErsoloPro_EtaPro->Fill(Eclusc_track[i], Dedx_track[i]);
          }
          */
        }
        else if(PionCentrCut->IsInside(Eclusc_track[i], Dedx_track[i])){
          dEdxErsoloPiondirty->Fill(Eclusc_track[i], Dedx_track[i]);
          pair<double,double> tempangle;
          tempangle.first=Thet_centr_track[i];
          tempangle.second=Phi_centr_track[i];
          pionangles.push_back(tempangle);
          /*
          if(nneutrons==1 && Eg_tag_strip[0]>=0.609){
            dEdxErsoloPion_pipn->Fill(Eclusc_track[i], Dedx_track[i]);
          }
          */
        }
        // qui aggiungiamo l'informazione su un carico centrale che non è nè un pione nè un protone
        else{
          double Etotpro = Eclusc_track[i] + RMP;
          TLorentzVector CandidateProton;
          double Ppro = sqrt(Etotpro*Etotpro-RMP*RMP);
          CandidateProton.SetPxPyPzE(Ppro*sin(Thet_centr_track[i]/180.*M_PI)*cos(Phi_centr_track[i]/180.*M_PI), Ppro*sin(Thet_centr_track[i]/180.*M_PI)*sin(Phi_centr_track[i]/180.*M_PI), Ppro*cos(Thet_centr_track[i]/180.*M_PI),Etotpro);
          ccharged.push_back(CandidateProton);
        }
        nccharged++;
      }
      // identifichiamo i deuteroni al centro(taglio di prova: tutti gli eventi sopra la banana dei protoni sono nuclei di deuterio)
      /*
      if(cartella=="2005_d2"){
        if(FitDeuCentr_2005_d2->Eval(Eclusc_track[i])<=Dedx_track[i]){
           double Etotdeu = Eclusc_track[i] +RMD;
           double Pdeu = sqrt(Etotdeu*Etotdeu-RMD*RMD);
           TLorentzVector CandidateDeuteron;
           CandidateDeuteron.SetPxPyPzE(Pdeu*sin(Thet_centr_track[i]/180.*M_PI)*cos(Phi_centr_track[i]/180.*M_PI), Pdeu*sin(Thet_centr_track[i]/180.*M_PI)*sin(Phi_centr_track[i]/180.*M_PI), Pdeu*cos(Thet_centr_track[i]/180.*M_PI),Etotdeu);
           cDeuteron.push_back(CandidateDeuteron);
        }
      }
      */
    }
    // solo per verifica
    //cout<<"########"<<endl;
    /*
    for(int i=0; i<N_traf; i++){
      cout<<"Iass_trf["<<i<<"]="<<int(Iass_trf[i])<<endl;
    }
    */
    //ciclo su tutte le traccie delle particelle in avanti
    for(int i =0; i<Nparf; i++){
     //cout<<i<<"  "<<Nparf<<"----"<< int(Index_trf[Nparf])<<endl;
     //     cout<< int(Iass_trf[Index_trf[Nparf]])<<endl;//ci aspettiamo numeri pari a 1 - 7
     //
     //  cout <<int(Ind_traf[Index_trf[Nparf]][2])<<endl;

     N_show_->Fill(Nshow); // filliamo con il numero di colpi nel Russian Wall

     int index_trf_=0;
     if(Index_trf[i]!=0){
       index_trf_ = Index_trf[i]-1;// associamo il valore di index_trf_ a quello della traccia del singolo evento e scaliamo il valore di Index_trf[i] di 1, perchè il Root parte da 0 e non da 1 come fa il Fortran
     }
      int index = int(Iass_trf[index_trf_]);

      ind_trf->Fill(index_trf_); // filliamo con l'indice assegnato alla traccia in base all'associazione dei rivelatori corrispondente
      Iass_trf_->Fill(index); // filliamo con l'indice asegnato alla traccia che identifica il tipo di particella


      // solo per verifica
      /*
      cout<<"Nparf="<<Nparf<<endl;
      cout<<"Index_trf["<<i<<"]="<<int(index_trf_)<<"  "<<endl;
      cout<<"Iass_trf["<<int(index_trf_)<<"]="<<int(Iass_trf[index_trf_])<<"  "<<endl;
      cout<<"index="<<index<<"  "<<endl;
      */
      //int indexRW = int(Ind_traf[Index_trf[i]][2]);
      int indexRW = int(Ind_traf[index_trf_][2]);
      //cout<<index<<endl;
      if(index==1){//neutri
        //double DEDX_TRACCIAF   = Eshow[indexRW]*1000.*Cos_trf[i][2];
        //double TOF_F           = Tof_trf[i]*fabs(cos(Theta_trf[i])); // per normalizzare il tempo di volo bisogna moltiplicare per il coseno di theta della traccia
        //double TOF_F2 = Tof_trf[i]*fabs(Cos_trf[i][2]);
        double DEDX_F_N = De_trf[i]; // perdite di energia dei neutri in avanti(nel prean fanciullo vengono utilizzate le stesse varibili per neutri e carichi sulla peridta di energia e di tempo di volo)
        double TOF_F_N = Tof_trf[i]; // tempo di volo dei neutri in avanti
        Dedx_Tof_idrun->Fill(TOF_F_N,DEDX_F_N,idrun);
        ddxtof_f->Fill(TOF_F_N,DEDX_F_N);
        E_show_->Fill(Eshow[i]); // filliamo con la deposizione di energia nel russian wall
        Theta_trf_fn->Fill(Theta_trf[i]);
        Phi_trf_fn->Fill(Phi_trf[i]);
        if(Tof_trf[i]>=12){  //regno dei neutroni
          double beta     = 335./(Tof_trf[i]*CLIGHT*1.E-09);
          if((1-beta*beta)>0){
            TLorentzVector CandidatefNeutron;
            double gamma = 1./sqrt(1-beta*beta);
            double ENE_FNeutron = gamma* RMN; //energia totale
            double Pfneu = sqrt(ENE_FNeutron*ENE_FNeutron-RMN*RMN);
            CandidatefNeutron.SetPxPyPzE(Pfneu*sin(Theta_trf[i]/180.*M_PI)*cos(Phi_trf[i]/180.*M_PI), Pfneu*sin(Theta_trf[i]/180.*M_PI)*sin(Phi_trf[i]/180.*M_PI), Pfneu*cos(Theta_trf[i]/180.*M_PI),ENE_FNeutron);
            fneutron.push_back(CandidatefNeutron);
            nneutrons++;
          }
        }
        else if(Tof_trf[i]>=7.5 && Tof_trf[i]<=12.5){//regno fotoni ...solo gli angoli
          pair<double,double> tempangle;
          tempangle.first=Theta_trf[i];
          tempangle.second=Phi_trf[i];
          fphotonangles.push_back(tempangle);
          nphotons++;
        }
      }
      if(index!=1){//particelle cariche, quelle per le quali tutti i rivelatori sensibili ai carichi hanno sparato

        // if(index==6||index==7){//particelle cariche, quelle per le quali tutti i rivelatori sensibili ai carichi hanno sparato
        /*
        if(index==4){
          cout<<"non dovrei essere qui"<<endl;
        }
        */
        if(index==5){
                DIST_WALL = 335.; //in cm
        }
        else{
                // For tracks n.2 (0-1-0), 3 (0-1-1), 6 (1-1-0) and 7 (1-1-1),
                //the distance for tof is the OW
                DIST_WALL = 301.53;
        }
        //double TOF_ch = Tof_trf[i]/cos(Theta_trf[i]); // tempo di volo non normalizzato alla direzione centrale
        //double DE_TRF_CH = De_trf[i]/cos(Theta_trf[i]); // perdita di energia non normalizzata alla direzione centrle
        Theta_trf_fch->Fill(Theta_trf[i]);
        Phi_trf_fch->Fill(Phi_trf[i]);
        ddxtof_fow->Fill(Tof_trf[i],De_trf[i]);
        if(cartella!="2005_d1"){  // nella cartella 2005_d1 non ci sono protoni rivelati in avanti
         if(ProtonForwCut->IsInside(Tof_trf[i], De_trf[i])){ //regno dei protoni in avanti
           ddxtof_fow_Pro->Fill(Tof_trf[i], De_trf[i]);
           pair<double,double> pangles;
           pangles.first = Theta_trf[i];
           pangles.second = Phi_trf[i];
           double beta     = DIST_WALL/(Tof_trf[i]*CLIGHT*1.E-09);
        	 if((1-beta*beta)>0){
        	  TLorentzVector CandidatefProton;
        	  double gamma = 1./sqrt(1-beta*beta);
        	  double ENE_FPROTON = gamma* RMP; //energia totale
        	  double Pfpro = sqrt(ENE_FPROTON*ENE_FPROTON-RMP*RMP);
        	  CandidatefProton.SetPxPyPzE(Pfpro*sin(Theta_trf[i]/180.*M_PI)*cos(Phi_trf[i]/180.*M_PI), Pfpro*sin(Theta_trf[i]/180.*M_PI)*sin(Phi_trf[i]/180.*M_PI), Pfpro*cos(Theta_trf[i]/180.*M_PI),ENE_FPROTON);
        	  proton.push_back(CandidatefProton);
            Tof_fpro.push_back(Tof_trf[i]);
            Tof_fch.push_back(Tof_trf[i]);
            fproangles.push_back(pangles);
        	  fpro++;
            fch++;
        	 }
         }
         if(PionForwCut->IsInside(Tof_trf[i], De_trf[i])){ //regno dei pioni in avanti
            ddxtof_fow_Pion->Fill(Tof_trf[i], De_trf[i]);
            pair<double,double> tempangle;
          	tempangle.first=Theta_trf[i];
          	tempangle.second=Phi_trf[i];
          	pionangles.push_back(tempangle);
            Tof_fch.push_back(Tof_trf[i]);
            fch++;
         }
         /*
         if(cartella!="2005_d2"){
           if(De_trf[i]>=0.007 && Tof_trf[i]>10.44){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="1999_d2"){
           if(De_trf[i]>=0.008 && Tof_trf[i]>=11){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="1999_d1"){
           if(De_trf[i]>=0.012 && Tof_trf[i]<=12.45){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="2001_d"){
           if(De_trf[i]>=0.007 && Tof_trf[i]<=10.84){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="2006_d"){
           if(De_trf[i]>=0.007 && Tof_trf[i]<=13.05){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="2002_d1"){
           if(De_trf[i]>=0.009 && Tof_trf[i]<=12.34){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="2002_d3"){
           if(De_trf[i]>=0.010 && Tof_trf[i]<=11.14){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         if(cartella!="2002_d2"){
           if(De_trf[i]>=0.005 && Tof_trf[i]<=9.76){
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
           }
         }
         */
         if(DeuForwCut!=0){
           if(DeuForwCut->IsInside(Tof_trf[i], De_trf[i])){ // regno dei deutoni in avanti
            double beta = DIST_WALL/(Tof_trf[i]*CLIGHT*1.E-09);
            pair<double,double> dangles;
            dangles.first= Theta_trf[i];
            dangles.second = Phi_trf[i];
            fdeuangles.push_back(dangles);
            Tof_fdeu.push_back(Tof_trf[i]);
            if((1-beta*beta)>0){
             TLorentzVector CandidatefDeu;
             double gamma = 1./sqrt(1-beta*beta);
             double ENE_FDEUTERON = gamma* RMD; // energia totale
             double Pfdeu = sqrt(ENE_FDEUTERON*ENE_FDEUTERON-RMD*RMD);
             //double Pfdeu = sqrt(ENE_FDEUTERON*ENE_FDEUTERON-RMP*RMP);
             double inc_Ed = (RMD*(DIST_WALL*1.E+09/pow(Tof_trf[i],2))*5*1.E-09+(RMD*DIST_WALL)/(2*Tof_trf[i])*1/sqrt(1-pow(DIST_WALL,2)/pow(Tof_trf[i],2)*pow(CLIGHT,2))*(pow(DIST_WALL,2)/pow(CLIGHT,2))*(2/pow(Tof_trf[i],3))*5*1.E-09)/(1-pow(DIST_WALL,2)/pow(Tof_trf[i]*CLIGHT,2));
             scr1<<inc_Ed<<endl;
             CandidatefDeu.SetPxPyPzE(Pfdeu*sin(Theta_trf[i]/180.*M_PI)*cos(Phi_trf[i]/180.*M_PI), Pfdeu*sin(Theta_trf[i]/180.*M_PI)*sin(Phi_trf[i]/180.*M_PI),Pfdeu*cos(Theta_trf[i]/180.*M_PI),ENE_FDEUTERON);
             fDeuteron.push_back(CandidatefDeu);
             Tof_fch.push_back(Tof_trf[i]);
             fch++;
            }
          }
         }
         /*
         if(!PionForwCut->IsInside(Tof_trf[i], De_trf[i]) && !ProtonForwCut->IsInside(Tof_trf[i], De_trf[i]) && !DeuForwCut->IsInside(Tof_trf[i], De_trf[i])){
           //Tof_fch.push_back(Tof_trf[i]);
           //fch++;
         }
         */
       }
      }
     }
      //tree->Fill();
      //bool val1 = CutEtapNeu(cphoton,fneutron,fDeuteron,proton,Eg_tag_strip[0]);
      //bool val2 = CutEtapPro(cphoton,fneutron,fDeuteron,proton,Eg_tag_strip[0]);
      //bool val3 = Cut1deu(proton,fneutron,fDeuteron);
      //bool val4 = Cut1deu_2ph(proton,fneutron,fDeuteron,cphoton,pionangles,fphotonangles);
      //bool val5 = Cut1deu_4ph(proton,fneutron,fDeuteron,cphoton,pionangles,fphotonangles);
      //bool val6 = Cut1pro_4ph(proton,fneutron,fDeuteron,cphoton,pionangles,fphotonangles);
      //Int_t *Mclus = MClus.data();
      /*
      if(val1==1){
        for(int i=0; i<MClus.size(); i++){
          scrivimi2<<Mclus[i]<<endl;
        }
        tree->Fill();
      }
      */
    /*
    // blocco che isola in maniera pulita gli eventi di tipo protone dai grafici dEdx vs Er e dE vs TOF applicando il taglio preliminare eventi gamma p eta p
    if(nphotons>=2 && Eg_tag_strip[0]>=0.708){

      for(int i=0; i<Nass_3; i++){
         if(Itipo_track[i]==13 || Itipo_track[i]==14){
          dEdxErsoloPro_EtaPro->Fill(Eclusc_track[i], Dedx_track[i]);
         }
      }
      for(int i=0; i<=Nparf; i++){
        int index_trf_=0;
        if(Index_trf[i]!=0){
          index_trf_ = Index_trf[i]-1;// associamo il valore di index_trf_ a quello della traccia del singolo evento e scaliamo il valore di Index_trf[i] di 1, perchè il Root parte da 0 e non da 1 come fa il Fortran
        }
        int index = int(Iass_trf[index_trf_]);
        if(index!=1){
         if(ProtonForwCut->IsInside(Tof_trf[i], De_trf[i])){
          ddxtofsoloPro_pipn->Fill(Tof_trf[i], De_trf[i]);
         }
        }
      }
    }
    */

    /*
    // blocco che filla il grafico dEdx vs Er selezionando solo gli eventi di tipo pione carico
    if(nneutrons==1 && cphoton.size()==0 && fphotonangles.size()==0 && proton.size()==0){
      for(int i=0; i<Nass_3; i++){
         if(Itipo_track[i]==13 || Itipo_track[i]==14){
          dEdxErsoloPion_pipn->Fill(Eclusc_track[i], Dedx_track[i]);
         }
       }
    }
    */
    //tree->Fill();
    /*
    if(fneutron.size()==1 && proton.size()==0 && fphotonangles.size()==0 && fDeuteron.size()==0){
     TLorentzVector *neutrone = fneutron.data();
     if(cutg1->IsInside(Eg_tag_strip[0],neutrone[0].Theta()*TMath::RadToDeg())){
       tree->Fill();
     }
    }
    */
    if(fch==1 && fphotonangles.size()==0 && cphoton.size()>=2){
        tree->Fill();
    }

  }

  scr1.close();
  scrivimi.close();
  scrivimi2.close();

  gStyle->SetOptStat("");
  //gStyle->SetFrameBorderMode(0);  // 0 = no border, 1 = black line, -1 = background fill
  //gStyle->SetFrameBorderSize(2);  // thickness
  // i due blocchi successivi pervono  a controllare i tagli che identificano i protoni e  i pioni in avanti e centrali
  TCanvas *c1 = new TCanvas("c1","",700,600);
  c1->SetBorderMode(0);
  c1->SetLogz();
  c1->SetLeftMargin(0.15);   // default ~0.1 : units in NDC fractions of the pad size
  c1->SetRightMargin(0.20);  // default ~0.1
  c1->SetTopMargin(0.05);    // default ~0.1
  c1->SetBottomMargin(0.15); // default ~0.1
  ProtonCentrCut->SetLineColor(2);
  PionCentrCut->SetLineColor(1);
  ProtonCentrCut->SetLineWidth(5);
  PionCentrCut->SetLineWidth(5);
  //protondxE->SetName("De_dx vs Er");
  protondxE->GetXaxis()->SetTitleSize(0.075);
  protondxE->GetYaxis()->SetTitleSize(0.075);
  protondxE->GetXaxis()->CenterTitle(1);
  protondxE->GetXaxis()->SetTitleOffset(0.9);
  protondxE->GetYaxis()->SetTitleOffset(0.9);
  protondxE->GetXaxis()->SetTitleFont(132);
  protondxE->GetYaxis()->SetTitleFont(132);
  protondxE->GetXaxis()->SetLabelFont(132);
  protondxE->GetYaxis()->SetLabelFont(132);
  protondxE->GetXaxis()->SetTitle("Er(GeV)");
  protondxE->GetYaxis()->SetTitle("dE/dx(MeV/cm)");
  protondxE->Draw("colz");
  ProtonCentrCut->Draw("same");
  PionCentrCut->Draw("same");

  TLegend *l = new TLegend(0.3,0.62,0.7,0.8);
  l->AddEntry(ProtonCentrCut,"Protons","l");
  l->AddEntry(PionCentrCut,"Pions","l");
  l->Draw("same");
  string sep="/home/thinkpadinfn/GRAAL/";
  string Name1 = str1 + str16;
  string Name2 = str1 + str17;
  c1->SaveAs(Name1.c_str());
  c1->SaveAs(Name2.c_str());

  //if(DeuForwCut!=0){
  TCanvas *c3 = new TCanvas("c3",str3.c_str(),700,600);
  c3->SetRightMargin(0.16);
  c3->SetLogz();
  c3->SetLeftMargin(0.15);   // default ~0.1 : units in NDC fractions of the pad size
  c3->SetRightMargin(0.15);  // default ~0.1
  c3->SetTopMargin(0.05);    // default ~0.1
  c3->SetBottomMargin(0.15); // default ~0.1
  ProtonForwCut->SetLineColor(2);
  PionForwCut->SetLineColor(5);
  ProtonForwCut->SetLineWidth(5);
  PionForwCut->SetLineWidth(5);
  ddxtof_fow->Draw("colz");
  //ddxtof_fow->SetName("#Delta E vs Tof");
  ddxtof_fow->GetXaxis()->SetTitle("Tof(ns)");
  ddxtof_fow->GetYaxis()->SetTitle("#Delta E(MeV)");
  ddxtof_fow->GetXaxis()->SetTitleSize(0.075);
  ddxtof_fow->GetYaxis()->SetTitleSize(0.075);
  ddxtof_fow->GetXaxis()->SetLabelSize(0.053);
  ddxtof_fow->GetYaxis()->SetLabelSize(0.053);
  ddxtof_fow->GetXaxis()->SetTitleFont(132);
  ddxtof_fow->GetYaxis()->SetTitleFont(132);
  ddxtof_fow->GetXaxis()->SetLabelFont(132);
  ddxtof_fow->GetYaxis()->SetLabelFont(132);
  //ddxtof_fow->GetYaxis()->SetRangeUser(0.,200.);
  //ddxtof_fow->GetXaxis()->SetRangeUser(0.,100.);
  ddxtof_fow->GetXaxis()->CenterTitle(1);
  ddxtof_fow->GetYaxis()->CenterTitle(1);
  ddxtof_fow->GetXaxis()->SetTitleOffset(0.8);
  ddxtof_fow->GetYaxis()->SetTitleOffset(0.8);
  //ddxtof_fow->SetTickLenght(0.05,"X");
  //DeuForwCut->SetLineColor(2);
  PionForwCut->Draw("same");
  ProtonForwCut->Draw("same");
  if(DeuForwCut!=0){
    DeuForwCut->Draw("same");
    DeuForwCut->SetLineWidth(5);
    DeuForwCut->SetLineColor(1);
  }

  TLegend *l2 = new TLegend(0.65,0.70,0.85,0.86);
  l2->AddEntry(ProtonForwCut,"Protons","l");
  l2->AddEntry(PionForwCut,"Pions","l");
  l2->AddEntry(DeuForwCut,"Deuterons","l");
  l2->Draw("same");
  string Name21 = str3 + str16;
  string Name22 = str3 + str17;
  c3->SaveAs(Name21.c_str());
  c3->SaveAs(Name22.c_str());
  //}

  TCanvas *c4 = new TCanvas("c4","",700,600);
  //c4->SetRightMargin(0.16);
  //c4->SetLogz();
  c4->SetLeftMargin(0.17);   // default ~0.1 : units in NDC fractions of the pad size
  c4->SetRightMargin(0.15);  // default ~0.1
  c4->SetTopMargin(0.05);    // default ~0.1
  c4->SetBottomMargin(0.15); // default ~0.1
  ddxtof_f->GetXaxis()->CenterTitle();
  ddxtof_f->GetXaxis()->SetTitleSize(0.075);
  ddxtof_f->GetYaxis()->SetTitleSize(0.075);
  ddxtof_f->GetXaxis()->SetLabelSize(0.065);
  ddxtof_f->GetYaxis()->SetLabelSize(0.065);
  ddxtof_f->GetXaxis()->SetTitleOffset(0.85);
  ddxtof_f->GetYaxis()->SetTitleOffset(0.75);
  ddxtof_f->GetXaxis()->SetTitleFont(132);
  ddxtof_f->GetYaxis()->SetTitleFont(132);
  ddxtof_f->GetXaxis()->SetLabelFont(132);
  ddxtof_f->GetYaxis()->SetLabelFont(132);
  ddxtof_f->GetYaxis()->SetRangeUser(-0.250,200);
  ddxtof_f->GetXaxis()->SetTitle("Tof(ns)");
  ddxtof_f->GetYaxis()->SetTitle("#Delta E(MeV)");
  ddxtof_f->GetYaxis()->CenterTitle();
  //ddxtof_f->GetXaxis()->SetTicksLenght(0.04);
  ddxtof_f->Draw();
  string Name31 = str2 + str16;
  string Name32 = str2 + str17;
  c4->SaveAs(Name31.c_str());
  c4->SaveAs(Name32.c_str());

  //TCanvas *c5 = new TCanvas("c5","",700,600);
  //CutEgThN->Draw();

  TFile *fileI = new TFile("../Tracks_spectra.root","update");
  protondxE->Write();
  dEdxErsoloProdirty->Write();
  dEdxErsoloPiondirty->Write();
  ddxtof_f->Write();
  ddxtof_fow->Write();
  ddxtof_fow_Pro->Write();
  ddxtof_fow_Pion->Write();
  ddxtofsoloPro_pipn->Write();
  fileI->Close();

  // il blocco sotto salva i tagli che identificano i carichi centrali e quelli in avanti dai grafici dE/dx vs Er e DeltaE vs TOF
  TFile *fileII = new TFile("../Cuts.root","update");
  ProtonCentrCut->Write();
  PionCentrCut->Write();
  ProtonForwCut->Write();
  PionForwCut->Write();
  fileII->Close();



  /*
  TFile *fileII = new TFile("../Forward_charged_tracks_spectra.root","update");
  ddxtof_fow_tracks_5_6->Write();
  ddxtof_fow_tracks_2_3->Write();
  ddxtof_fow_tracks_4->Write();
  fileII->Close();
  */

  /*
  TFile *fileIII = new TFile("../Centr_Tracks_dedx_Er_Ind_bar_1998_uv.root","recreate");
  protondxE_Ind_bar->Write();
  fileIII->Close();
  */

  /*
  TFile *fileIV = new TFile("Forward_neutr_spectrum_1998_uv.root","recreate");
  ddxtof_f->Write();
  fileIV->Close();
  */

  /*
  TFile *fileV = new TFile(str12.c_str(),"recreate");
  ddxtof_fow->Write();
  Theta_trf_fch->Write();
  Phi_trf_fch->Write();
  N_show_->Write();
  E_show_->Write();
  Iass_trf_->Write();
  ind_trf->Write();
  ddxtof_f->Write();
  Theta_trf_fn->Write();
  Phi_trf_fn->Write();

  fileV->Close();
  */

  /*
  TFile *fileVI = new TFile("Forw_Tracks.root","update");
  ddxtof_fow->Write();
  Theta_trf_fch->Write();
  Phi_trf_fch->Write();
  N_show_->Write();
  E_show_->Write();
  Iass_trf_->Write();
  ind_trf->Write();
  ddxtof_f->Write();
  Theta_trf_fn->Write();
  Phi_trf_fn->Write();

  fileVI->Close();
  */

  /*
  TFile *fileVII = new TFile("../beamE_spectra.root","update");
  BeamE->Write();
  fileVII->Close();
  */

  /*
  TFile *fileVIII = new TFile("../Output_Forward_Tracks.root","update");
  Tof_vs_Dedx_vs_idrun_->Write();
  fileVIII->Close();
  */

  /*
  TFile *file9 = new TFile("../Tracks_dedx_vs_Er_vs_Ibar.root","update");
  protondxE_Ind_bar->Write();
  file9->Close();
  */

  dati->Write();
  dati->Close();


}
