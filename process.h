///////////////////////////////////////////////////
// Header file contenente l'argoritmo di processing
// l'algoritmo prende un albero e lo cerca di
// analizzare
///////////////////////////////////////////////////


void Analysis::process(TTree *alb, string root_file, string cartella){

  
  //Funzione di inizializzazione dell'albero passato
  Analysis::Init(alb);

  //Inizio algoritmo
  double RMP    = 0.9382720813;
  double RMN    = 0.9395654133;
  double RMD = 1.877;
  double CLIGHT = 29979245800.; //! cm/sec
  double DIST_WALL;
  double percent = 10.0;

  TCutG *ProtonCentrCut   = myProtonCentrCut();
  TCutG *PionCentrCut     = myPionCentrCut();
  TCutG *ProtonForwCut    = myProtonForwCut(cartella);
  TCutG *PionForwCut      = myPionForwCut();
  TF1 *FitForwDeu = CutDeuForw(cartella);
  
  TF1 *f = CutDeuForw(cartella);
  
  TH2D *protondxE         = new TH2D("protondxE","protondxE",100,0,1.2,100,0,20);
  TH2D *protondxEsoloPro  = new TH2D("protondxEsoloPro","protondxEsoloPro",100,0,1.2,100,0,20);
  TH2D *protondxEsoloPio  = new TH2D("protondxEsoloPio","protondxEsoloPio",100,0,1.2,100,0,20);
  TH2D *ddxtof_f          = new TH2D("ddxtof_f","ddxtof_f",100,0,0,100,0,0);
  TH2D *ddxtof_fow        = new TH2D("ddxtof_fow","ddxtof_fow",100,0,0,100,0,0);

  TFile *dati = new TFile(root_file.c_str(),"recreate");
  TTree *tree = new TTree("h80","Graal data Analysis");

  int idrun, idevt, ipol;

  vector<TLorentzVector> cphoton;
  vector<TLorentzVector> proton;
  // vector<TLorentzVector> cproton;
  vector<pair<double,double> > pionangles;
  vector<pair<double,double> > fphotonangles;
  // vector<TLorentzVector> fproton;
  vector<TLorentzVector> fneutron;
  vector<TLorentzVector> fDeuteron;
  
  TLorentzVector beam;

  tree->Branch("beam",    "TLorentzVector", &beam);
  tree->Branch("idrun",   &idrun, "idrun/I");   // numero del run
  tree->Branch("idevt",   &idevt, "idevt/I");   // numero dati dell'evento 
  tree->Branch("ipol",    &ipol,  "ipol/I");    // polarizzazione del fascio: 0 verticale, 1 orizzontale, 2 bremsstrahlung 
  tree->Branch("cphoton", &cphoton);
  // tree->Branch("cproton", &cproton);
  tree->Branch("proton",  &proton);
  // tree->Branch("fproton", &fproton);
  tree->Branch("fneutron",&fneutron);
  tree->Branch("pionangles",    &pionangles);
  tree->Branch("fphotonangles", &fphotonangles);
  tree->Branch("fDeuteron",&fDeuteron);

  if (fChain == 0) return;
  Long64_t nentries = fChain->GetEntriesFast();
  Long64_t nbytes = 0, nb = 0;

  for (Long64_t jentry=0; jentry<nentries; jentry++) {
    Long64_t ientry = LoadTree(jentry);
    if (ientry < 0) break;
    nb = fChain->GetEntry(jentry);   nbytes += nb;

    cphoton.clear();
    proton.clear();
    //cproton.clear();
    //fproton.clear();
    fneutron.clear();
    pionangles.clear();
    fphotonangles.clear();
    fDeuteron.clear();


    // if (Cut(ientry) < 0) continue;
    idrun = Idrun;
    idevt = Idevt;
    ipol  = int(Ipol);

    int fpro = 0;
    int cpro = 0;

    beam.SetPxPyPzE(0.,0.,Eg_tag_strip[0],Eg_tag_strip[0]);

    //fa un ciclo su tutte le traccie rivelate al centro
    for(int i=0; i<Nass_3; i++) {
      if(Itipo_track[i]==11) {
        TLorentzVector CandidatePhoton;
        CandidatePhoton.SetPxPyPzE(Eclusc_track[i]*sin(Thet_centr_track[i]/180.*M_PI)*cos(Phi_centr_track[i]/180.*M_PI),Eclusc_track[i]*sin(Thet_centr_track[i]/180.*M_PI)*sin(Phi_centr_track[i]/180.*M_PI),Eclusc_track[i]*cos(Thet_centr_track[i]/180.*M_PI),Eclusc_track[i]);
        cphoton.push_back(CandidatePhoton);
      }
      if(Itipo_track[i]==13||Itipo_track[i]==14) {
        protondxE->Fill(Eclusc_track[i], Dedx_track[i]);
        if(ProtonCentrCut->IsInside(Eclusc_track[i], Dedx_track[i])) {
          protondxEsoloPro->Fill(Eclusc_track[i], Dedx_track[i]);
          //   double Etotpro = Eclusc_track[i] + Dedx_track[i]/(2*sin(Thet_centr_track[i]/180.*M_PI)*1000.) + RMP;
          double Etotpro = Eclusc_track[i] + RMP;
          TLorentzVector CandidateProton;
          double Ppro = sqrt(Etotpro*Etotpro-RMP*RMP);
          CandidateProton.SetPxPyPzE(Ppro*sin(Thet_centr_track[i]/180.*M_PI)*cos(Phi_centr_track[i]/180.*M_PI), Ppro*sin(Thet_centr_track[i]/180.*M_PI)*sin(Phi_centr_track[i]/180.*M_PI), Ppro*cos(Thet_centr_track[i]/180.*M_PI),Etotpro);
          proton.push_back(CandidateProton);
          cpro++;
        }
        if(PionCentrCut->IsInside(Eclusc_track[i], Dedx_track[i])) {
          protondxEsoloPio->Fill(Eclusc_track[i], Dedx_track[i]);
          pair<double,double> tempangle;
          tempangle.first=Thet_centr_track[i];
          tempangle.second=Phi_centr_track[i];
          pionangles.push_back(tempangle);
        }
      }
    }
    
     
    //ciclo su tutte le traccie delle particelle in avanti
    for(int i =0; i< Nparf; i++) {
      //cout<<i<<"  "<<Nparf<<"----"<< int(Index_trf[Nparf])<<endl;
      //     cout<< int(Iass_trf[Index_trf[Nparf]])<<endl;//ci aspettiamo numeri pari a 1 - 7
      //
      //  cout <<int(Ind_traf[Index_trf[Nparf]][2])<<endl;
      int index = int(Iass_trf[Index_trf[i]]);
      int indexRW = int(Ind_traf[Index_trf[i]][2]);
      if(index==1) {//neutri
        double DEDX_TRACCIAF   = Eshow[indexRW]*1000.*Cos_trf[i][2];
        double TOF_F           = Tof_trf[i];
        ddxtof_f->Fill(TOF_F,DEDX_TRACCIAF);

        if(Tof_trf[i]>=13.5) {//regno dei neutroni
          double beta     = 335./(Tof_trf[i]*CLIGHT*1.E-09);
          if((1-beta*beta)>0) {
            TLorentzVector CandidatefNeutron;
            double gamma = 1./sqrt(1-beta*beta);
            double ENE_FNeutron = gamma* RMP; //energia totale
            double Pfneu = sqrt(ENE_FNeutron*ENE_FNeutron-RMP*RMP);
            CandidatefNeutron.SetPxPyPzE(Pfneu*sin(Theta_trf[i]/180.*M_PI)*cos(Phi_trf[i]/180.*M_PI), Pfneu*sin(Theta_trf[i]/180.*M_PI)*sin(Phi_trf[i]/180.*M_PI), Pfneu*cos(Theta_trf[i]/180.*M_PI),ENE_FNeutron);
            fneutron.push_back(CandidatefNeutron);

          }
        }
        else{//regno fotoni ...solo gli angoli
          pair<double,double> tempangle;
          tempangle.first=Theta_trf[i];
          tempangle.second=Phi_trf[i];
          fphotonangles.push_back(tempangle);
        }

      }
      if(index!=1) {//particelle cariche, quelle per le quali tutti i rivelatori sensibili ai carichi hanno sparato

        // if(index==6||index==7){//particelle cariche, quelle per le quali tutti i rivelatori sensibili ai carichi hanno sparato

          if(index==5) {
                  DIST_WALL = 335.; //in cm
          }
          else{
                  // For tracks n.2 (0-1-0), 3 (0-1-1), 6 (1-1-0) and 7 (1-1-1),
                  //the distance for tof is the OW
                  DIST_WALL = 301.53;
          }
        
        
              
                if(cartella!="2005_d1"){  // non ci sono deuteroni in avanti nei dati contenuti in questa cartella
                   if(FitForwDeu->Eval(Tof_trf[i])<De_trf[i]){
                  
                       double beta = DIST_WALL/(Tof_trf[i]*CLIGHT*1.E-09);

         		   if((1-beta*beta)>0) {
			     TLorentzVector CandidatefDeuteron;
			     double gamma = 1./sqrt(1-beta*beta);
			     double ENE_FDEUTERON = gamma* RMD; //energia totale
			     double Pfdeu = sqrt(ENE_FDEUTERON*ENE_FDEUTERON-RMD*RMD);
			     CandidatefDeuteron.SetPxPyPzE(Pfdeu*sin(Theta_trf[i]/180.*M_PI)*cos(Phi_trf[i]/180.*M_PI), Pfdeu*sin(Theta_trf[i]/180.*M_PI)*sin(Phi_trf[i]/180.*M_PI), 			Pfdeu*cos(Theta_trf[i]/180.*M_PI),ENE_FDEUTERON);
			    fDeuteron.push_back(CandidatefDeuteron); 
                  
                           }
              
                      }
		 }
        
     if(cartella!="2005_d1"){  // non ci sono protoni in avanti nei dati contenuti in questa cartella
        if(ProtonForwCut->IsInside(Tof_trf[i], De_trf[i])) { //regno dei protoni in avanti

          double beta     = DIST_WALL/(Tof_trf[i]*CLIGHT*1.E-09);

          if((1-beta*beta)>0) {
            TLorentzVector CandidatefProton;
            double gamma = 1./sqrt(1-beta*beta);
            double ENE_FPROTON = gamma* RMP; //energia totale
            double Pfpro = sqrt(ENE_FPROTON*ENE_FPROTON-RMP*RMP);
            CandidatefProton.SetPxPyPzE(Pfpro*sin(Theta_trf[i]/180.*M_PI)*cos(Phi_trf[i]/180.*M_PI), Pfpro*sin(Theta_trf[i]/180.*M_PI)*sin(Phi_trf[i]/180.*M_PI), Pfpro*cos(Theta_trf[i]/180.*M_PI),ENE_FPROTON);
            proton.push_back(CandidatefProton);
            fpro++;
          }

        }
      }	     
        
        if(PionForwCut->IsInside(Tof_trf[i], De_trf[i])) { //regno dei pioni in avanti
          pair<double,double> tempangle;
          tempangle.first=Theta_trf[i];
          tempangle.second=Phi_trf[i];
          pionangles.push_back(tempangle);

        }

      }


    }

    //  if(cpro+fpro==1)
    //cout<<contapro<<endl;
    tree->Fill(); //e qui stampare il tree in modo che fotografa il vettore di photon!!
  }
 
 
  dati->Write();
  dati->Close();

  // TCanvas(root_file.c_str(), "");

  // protondxE->Draw("colz");
  // protondxEsoloPro->Draw("same");
  // protondxEsoloPio->Draw("same");
  //
  // ddxtof_f->Draw();
  // ddxtof_fow->Draw("colz");

}
