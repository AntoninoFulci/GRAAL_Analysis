void genEtapPro(){
  TLorentzVector beam;
  TLorentzVector Target(0.,0.,0.,0.93827208816);
  TLorentzVector W;
  TLorentzVector Eta;
  TLorentzVector Proton;

  double masses[2]={0.547862,0.93827208816};
  TGenPhaseSpace *gammaPEtaP = new TGenPhaseSpace();

  TH2D *EgThetaP = new TH2D("EgThetaP","",100,0.,0.,100,0.,0.);

  TRandom genero(0);

  for(int i=0; i<=10000; i++){
    double Eg = genero.Uniform(0.,1.600);
    beam.SetPxPyPzE(0.,0.,Eg,Eg);
    W = beam + Target;
    gammaPEtaP->SetDecay(W,2,masses);
    gammaPEtaP->Generate();
    Eta = *gammaPEtaP->GetDecay(0);
    Proton = *gammaPEtaP->GetDecay(1);

    EgThetaP->Fill(beam.E(),Proton.Theta()*TMath::RadToDeg());
  }

  TCanvas *c1 = new TCanvas("c1","",600,700);
  EgThetaP->Draw();
}
