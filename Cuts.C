//#include "CutEgThetaN.C"
//#include "CutEgEn.C"
void printcuts(string p){
  //TCutG *cuts[2] ={"CutEgThN","CutEgEn"};
  /*
  // taglio Energia gamma vs angolo theta del neutrone
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

  // taglio energia del gamma vs energia del neutrone
  TCutG *CutEgEn = new TCutG("CutEgEn",24);
  CutEgEn->SetVarX("beam energy(GeV)");
  CutEgEn->SetVarY("neutron energy(GeV)");
  CutEgEn->SetTitle("Graph");
  CutEgEn->SetFillStyle(1000);
  CutEgEn->SetPoint(0,1.6031,1.04328);
  CutEgEn->SetPoint(1,1.6031,1.12172);
  CutEgEn->SetPoint(2,1.60343,1.2554);
  CutEgEn->SetPoint(3,1.60276,1.3935);
  CutEgEn->SetPoint(4,1.6031,1.48961);
  CutEgEn->SetPoint(5,1.5865,1.47525);
  CutEgEn->SetPoint(6,1.56043,1.43438);
  CutEgEn->SetPoint(7,1.53029,1.39681);
  CutEgEn->SetPoint(8,1.50591,1.35925);
  CutEgEn->SetPoint(9,1.48525,1.32169);
  CutEgEn->SetPoint(10,1.46866,1.29517);
  CutEgEn->SetPoint(11,1.45376,1.2554);
  CutEgEn->SetPoint(12,1.44631,1.22004);
  CutEgEn->SetPoint(13,1.44428,1.18138);
  CutEgEn->SetPoint(14,1.44834,1.13608);
  CutEgEn->SetPoint(15,1.46392,1.10625);
  CutEgEn->SetPoint(16,1.49304,1.08084);
  CutEgEn->SetPoint(17,1.54147,1.05322);
  CutEgEn->SetPoint(18,1.56144,1.04107);
  CutEgEn->SetPoint(19,1.5733,1.03665);
  CutEgEn->SetPoint(20,1.59328,1.03333);
  CutEgEn->SetPoint(21,1.60411,1.03554);
  CutEgEn->SetPoint(22,1.60445,1.04659);
  CutEgEn->SetPoint(23,1.6031,1.04328);
  */

  TFile *f = new TFile(p.c_str(),"read");
  TH1D *h1 = (TH1D*) f->Get("EgThetaNeu");
  TH1D *h2 = (TH1D*) f->Get("EgEn");
  TCutG *cutg1 = (TCutG*) f->Get("CutEgThn");
  TCutG *cutg2 = (TCutG*) f->Get("CutEgEn");
  cutg1->SetName("beam energy(GeV) #theta_{n}(degree)");
  cutg2->SetName("beam energy(GeV) Neutron energy(GeV)");
  TH1D *h[2]={h1,h2};
  TCutG *cuts[2] = {cutg1,cutg2};
  h1->SetName("EgThetaNeu");
  h2->SetName("EgEn");

  for(int i=0; i<2; i++){
    double myrightmargin = 0.16;
    double myleftmargin = 0.20;
    double mytopmargin = 0.12;
    double mybottommargin = 0.20;

    int mytextfont = 132;
    double mylabelsize = 0.05;
    double mytitlesize = 0.063;

    TCanvas *Scatola = new TCanvas("Scatola","",700,600);
    gStyle->SetOptStat(0);
    Scatola->SetRightMargin(myrightmargin);
    Scatola->SetLeftMargin(myleftmargin);
    Scatola->SetTopMargin(mytopmargin);
    Scatola->SetBottomMargin(mybottommargin);
    string titx = cuts[i]->GetName();
    string tity = cuts[i]->GetName();
    titx = titx.substr(0,16);
    tity = tity.substr(16);
    h[i]->GetXaxis()->SetTitleFont(132);
    h[i]->GetYaxis()->SetTitleFont(132);
    h[i]->GetXaxis()->SetLabelFont(132);
    h[i]->GetYaxis()->SetLabelFont(132);
    h[i]->GetXaxis()->SetLabelSize(mylabelsize);
    h[i]->GetYaxis()->SetLabelSize(mylabelsize);
    h[i]->GetXaxis()->SetTitleSize(mytitlesize);
    h[i]->GetYaxis()->SetTitleSize(mytitlesize);
    h[i]->GetXaxis()->CenterTitle();
    h[i]->GetXaxis()->SetTitleOffset(1.02);
    h[i]->GetXaxis()->SetTitle(titx.c_str());
    h[i]->GetYaxis()->SetTitleOffset(1.20);
    h[i]->GetYaxis()->CenterTitle();
    h[i]->GetYaxis()->SetTitle(tity.c_str());
    h[i]->Draw("colz");
    cuts[i]->Draw("same");
    string s = h[i]->GetName();
    string s1 = s + "_Cut" + ".pdf";
    string s2 = s + "_Cut" + ".png";
    Scatola->SaveAs(s1.c_str());
    Scatola->SaveAs(s2.c_str());

    delete Scatola;
  }

  f->Close();
  delete f;
}
TCutG *CutEgThetaN(string p){
  TFile *f = new TFile(p.c_str(),"read");
  TCutG *c1 = (TCutG*) f->Get("CutEgThn");
  TCutG *cutg1 = (TCutG*)c1->Clone();
  f->Close();
  return cutg1;
  delete f;
  delete c1;
  delete cutg1;
}
TCutG *CutEgEn(string p){
  TFile *f = new TFile(p.c_str(),"read");
  TCutG *c2 = (TCutG*) f->Get("CutEgEn");
  TCutG *cutg2 = (TCutG*)c2->Clone();
  f->Close();
  return cutg2;
  delete f;
  delete c2;
  delete cutg2;
}
