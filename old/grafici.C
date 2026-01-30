#include "cut.h"
void Forw_charged_1999_d1_Cuts(){

TCutG *Cut1 = myPionForwCut("1999_d1");
Cut1->SetLineColor(1);
TCutG *Cut2 = myProtonForwCut("1999_d1");
Cut2->SetLineColor(7);
TCutG *Cut3 = myDeuForwCut("1999_d1");
Cut3->SetLineColor(2);

TFile pina("Forw_tracks_1999_d1.root","read");

string s1 = "ddxtof_fow_";
string s2 = s1 + "1999_d1";

TH2D *i9 = (TH2D*) pina.Get(s2.c_str());

//impostazioni generali di estetica
int mymarkerstyle=20;
float mymarkersize=1.;
float mytextsize=0.059;
int mytextfont=132; //è il times new roman...ottimo per gli articoli o le relazioni
                    // per le presentazioni si prefiscono i caratteri sans serif ->senza grazia ->più leggibile

//Scatola che contiene il grafico
TCanvas *Scatola = new TCanvas("Scatola","Scatola",600,500); //costruttore 600pt x 550 pt
gStyle->SetOptStat(0); //non voglio che mi metti il riquadro con la statistica
Scatola->SetLogz();
Scatola->SetFillColor(0);//il fondo del grafico con 0 è bianco...in teoria lo potete cambiare
Scatola->SetBorderMode(0);//mette dei bordi attorno alla figura...0 nessun bordo
Scatola->SetBorderSize(2); //spessore del bordo
Scatola->SetLeftMargin(0.20); //spazio a sinistra della figura ...20% della larghezza
Scatola->SetRightMargin(0.06);// 5% della larghezza a destra
Scatola->SetTopMargin(0.04); //3% della altezza lato superiore
Scatola->SetBottomMargin(0.17); //12% dell'altezza lato inferiore
Scatola->SetTickx(1);
Scatola->SetTicky(1);

//uso il primo istogramma che plotto per definire tutto su assi titoli etc
i9->GetYaxis()->SetTitleSize(mytextsize); //controllo sulla dimension del titolo dell'asse
i9->GetXaxis()->SetTitleSize(mytextsize);
i9->GetXaxis()->SetLabelSize(mytextsize);//cotrollo sulla dimensione dei numeretti dell'asse
i9->GetYaxis()->SetLabelSize(mytextsize);
i9->GetXaxis()->SetTitleFont(mytextfont);//controllo sul carattere usato per il titolo dell'asse
i9->GetYaxis()->SetTitleFont(mytextfont);
i9->GetXaxis()->SetLabelFont(mytextfont);//controllo sul carattere usato per i numeretti dell'asse
i9->GetYaxis()->SetLabelFont(mytextfont);
i9->GetXaxis()->SetNdivisions(908); //suddivisione dei numeri sull'asse x---es 0 a 10 a passo di 1, e ogni passo diviso in 5
i9->GetXaxis()->CenterTitle(1);//che il titolo dell'asse lo voglio quindi 1, se non lo volessi metterei 0
i9->GetYaxis()->CenterTitle(1);
i9->SetTitle("");
//i9->GetXaxis()->SetRangeUser(0.,175.);
//i9->GetYaxis()->SetRangeUser(0.,340.);
i9->SetContour(20);
i9->GetXaxis()->SetTitle("Tof(ns)");
i9->GetYaxis()->SetTitle("DE/dx(MeV/cm)");
i9->GetXaxis()->SetTitleSize(0.063);
i9->GetYaxis()->SetTitleSize(0.063);
i9->SetLineColor(1);//nero
i9->SetLineWidth(1);
i9->GetXaxis()->SetTitleOffset(0.9);
i9->GetYaxis()->SetTitleOffset(0.9);

i9->Draw("colz");
Cut1->Draw("same");
Cut2->Draw("same");
Cut3->Draw("same");

TLegend *leg = new TLegend(0.5,0.82,0.9,0.95,NULL,"brNDC"); //this class is for the leggend
leg->SetBorderSize(0);//dimensione del bordo
leg->SetLineColor(1); //colore del bordo
leg->SetLineStyle(1); //stile del bordo
leg->SetLineWidth(1); // lo spessore
leg->SetFillColor(0); //colore dello sfondo
leg->SetTextSize(0.05); //dimensione del testo in percentuale dimensione della figura
leg->SetFillStyle(1001); //non me lo ricordo
leg->SetTextFont(132); // il font dell'inserto...times new roman
///              oggetto  "descrizione dell'oggetto", il tipo di simbolo l linea p per punto
leg->AddEntry(Cut1,"Pions" ,"l");
leg->AddEntry(Cut2,"Protons","l");
leg->AddEntry(Cut3,"Deuterons","l");

leg->Draw("same");

string s3 = i9->GetName();
s3 = s3 + ".png";
Scatola->SaveAs(s3.c_str());



/*
TPaveText *pt1 = new TPaveText(100,0.12,160,0.23,"br");
pt1->SetFillColor(0);
pt1->SetLineColor(0);
pt1->SetShadowColor(0);
pt1->SetTextFont(132);
pt1->SetTextSize(0.072);
text = pt1->AddText("<#theta_{#eta'}^{c.m.}>=132.5");
text = pt1->AddText("Chi square = ");
pt1->Draw();
*/
//pina.Close();

}
