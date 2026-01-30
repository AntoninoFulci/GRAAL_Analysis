// funzione che assume in input in odine: il vettore dei fotoni, il vetotre dei neutroni in avanti, il vettore dei deutoni in avanti, e ritorna 1 se l'evento rispetta le condizioni imposte e sia contenuto all'interno della regione simulata Eg vs theta Neu
bool CutEtapNeu(vector<TLorentzVector> cphoton, vector<TLorentzVector> fneutron, vector<TLorentzVector> fDeuteron, vector<TLorentzVector> proton, double Eg){
  bool val=0;

  TCutG *cutg = new TCutG("cutg",22);
  cutg->SetVarX("beam energy(GeV)");
  cutg->SetVarY("neutron theta(degree)");
  cutg->SetTitle("Graph");
  cutg->SetFillStyle(1000);
  //cutg->SetPoint(0,1.43954,0.158279);
  cutg->SetPoint(1,1.44292,2.79627);
  cutg->SetPoint(2,1.44631,4.16599);
  cutg->SetPoint(3,1.4497,5.28206);
  cutg->SetPoint(4,1.45681,6.80398);
  cutg->SetPoint(5,1.46223,8.07224);
  cutg->SetPoint(6,1.47848,10.4566);
  cutg->SetPoint(7,1.48864,11.7756);
  cutg->SetPoint(8,1.50354,13.6526);
  cutg->SetPoint(9,1.51065,14.6165);
  cutg->SetPoint(10,1.52555,15.8847);
  cutg->SetPoint(11,1.5479,17.6096);
  cutg->SetPoint(12,1.56483,18.9286);
  cutg->SetPoint(13,1.60513,21.668);
  cutg->SetPoint(14,1.60377,10);
  cutg->SetPoint(15,1.60547,-0.298295);
  cutg->SetPoint(16,1.59226,-0.0446428);
  cutg->SetPoint(17,1.56111,-0.146104);
  cutg->SetPoint(18,1.52758,-0.349026);
  cutg->SetPoint(19,1.48932,-0.146104);
  cutg->SetPoint(20,1.47848,0.0568182);
  //cutg->SetPoint(21,1.43954,0.158279);
  cutg->SetPoint(1,1.44292,2.79627);

  //cutg->SaveAs("CutEgThetaN.C");

  //TCanvas *c1 = new TCanvas("c1","",700,600);
  //cutg->SetName("CutEgThetaN");
  //cutg->Draw("same");

  //delete(c1);

  if(cphoton.size()>=2 && fneutron.size()==1 && proton.size()==0 && fDeuteron.size()==0){
   TLorentzVector *neutrone = fneutron.data();
   if(cutg->IsInside(Eg,neutrone[0].Theta()*TMath::RadToDeg())){
    val=1;
   }
  }
  return val;
}
