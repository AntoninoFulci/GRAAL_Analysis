/////////////////////////////////////////////////////////
// File contente i cut utilizzati nel l'algorimo
// di progessing dei dati
///////////////////////////////////////////////////

#include "TCutG.h"
#include "cutP/cutP1998_uv.C"
#include "cutP/cutP1999_d1.C"
#include "cutP/cutP1999_d2.C"
#include "cutP/cutP1999_uv.C"
#include "cutP/cutP1999_vis.C"
#include "cutP/cutP2000_fuv.C"
#include "cutP/cutP2000_uv1.C"
#include "cutP/cutP2000_uv2.C"
#include "cutP/cutP2000_vis.C"
#include "cutP/cutP2001_d.C"
#include "cutP/cutP2001_uv.C"
#include "cutP/cutP2002_d2.C"
#include "cutP/cutP2002_d3.C"
#include "cutP/cutP2002_uv1.C"
#include "cutP/cutP2002_uv2.C"
#include "cutP/cutP2002_vis1.C"
#include "cutP/cutP2002_vis2.C"
#include "cutP/cutP2003_vis.C"
#include "cutP/cutP2005_d2.C"
#include "cutP/cutP2006_d.C"
#include "cutP/cutP2002_d1.C"
#include "cutP/ForwDeuFit.C"


 TCutG *myProtonCentrCut(){
   TCutG *ProtonCentrCut = new TCutG("myProtonCentrCut",31);
   ProtonCentrCut->SetVarX("protondxE");
   ProtonCentrCut->SetVarY("");
   ProtonCentrCut->SetTitle("Graph");
   ProtonCentrCut->SetFillStyle(1000);
   ProtonCentrCut->SetLineColor(2);
   ProtonCentrCut->SetPoint(0,0.033026,11.5373);
   ProtonCentrCut->SetPoint(1,0.0248915,12.5454);
   ProtonCentrCut->SetPoint(2,0.0216377,13.9315);
   ProtonCentrCut->SetPoint(3,0.0175705,14.6371);
   ProtonCentrCut->SetPoint(4,0.0151301,15.4688);
   ProtonCentrCut->SetPoint(5,0.0135032,16.628);
   ProtonCentrCut->SetPoint(6,0.0143167,17.7621);
   ProtonCentrCut->SetPoint(7,0.0289588,16.9052);
   ProtonCentrCut->SetPoint(8,0.0370933,14.7127);
   ProtonCentrCut->SetPoint(9,0.0582429,12.1673);
   ProtonCentrCut->SetPoint(10,0.0972885,9.34476);
   ProtonCentrCut->SetPoint(11,0.152603,7.17742);
   ProtonCentrCut->SetPoint(12,0.221746,5.64012);
   ProtonCentrCut->SetPoint(13,0.299837,4.95968);
   ProtonCentrCut->SetPoint(14,0.379555,4.22883);
   ProtonCentrCut->SetPoint(15,0.43487,3.87601);
   ProtonCentrCut->SetPoint(16,0.490998,3.52319);
   ProtonCentrCut->SetPoint(17,0.498319,3.06956);
   ProtonCentrCut->SetPoint(18,0.48205,2.71673);
   ProtonCentrCut->SetPoint(19,0.412907,3.17036);
   ProtonCentrCut->SetPoint(20,0.337256,3.27117);
   ProtonCentrCut->SetPoint(21,0.281941,3.47278);
   ProtonCentrCut->SetPoint(22,0.221746,4.02722);
   ProtonCentrCut->SetPoint(23,0.169685,4.48085);
   ProtonCentrCut->SetPoint(24,0.120065,5.48891);
   ProtonCentrCut->SetPoint(25,0.0875271,6.64819);
   ProtonCentrCut->SetPoint(26,0.0696312,7.98387);
   ProtonCentrCut->SetPoint(27,0.0452278,9.31956);
   ProtonCentrCut->SetPoint(28,0.033026,10.8317);
   ProtonCentrCut->SetPoint(29,0.0232646,12.5454);
   ProtonCentrCut->SetPoint(30,0.033026,11.5373);

   return ProtonCentrCut;
}

TCutG *myPionCentrCut(){
  TCutG *PionCentrCut = new TCutG("myPionCentrCut",18);
  PionCentrCut->SetVarX("");
  PionCentrCut->SetVarY("");
  PionCentrCut->SetNameTitle("PionCentrCut");
  PionCentrCut->SetFillStyle(1000);
  PionCentrCut->SetPoint(0,0.0171944,8.08926);
  PionCentrCut->SetPoint(1,0.0361938,6.28063);
  PionCentrCut->SetPoint(2,0.0665928,4.76371);
  PionCentrCut->SetPoint(3,0.0979417,3.85939);
  PionCentrCut->SetPoint(4,0.16159,3.1301);
  PionCentrCut->SetPoint(5,0.210038,2.83839);
  PionCentrCut->SetPoint(6,0.210038,2.83839);
  PionCentrCut->SetPoint(7,0.299335,2.83839);
  PionCentrCut->SetPoint(8,0.359183,2.7217);
  PionCentrCut->SetPoint(9,0.44563,2.78005);
  PionCentrCut->SetPoint(10,0.498828,2.22579);
  PionCentrCut->SetPoint(11,0.498828,2.22579);
  PionCentrCut->SetPoint(12,0.500728,1.55484);
  PionCentrCut->SetPoint(13,0.214788,1.32147);
  PionCentrCut->SetPoint(14,0.0086447,1.02975);
  PionCentrCut->SetPoint(15,0.00959467,8.06009);
  PionCentrCut->SetPoint(16,0.0171944,8.08926);
  PionCentrCut->SetPoint(17,0.0171944,8.08926);

  return PionCentrCut;
}

TCutG *myProtonForwCut(string cartella){
  // cout<<"Il nome della cartella del cut è: "<<cartella<<endl;
  map<string, TCutG*> ProtonCut;
  ProtonCut["1998_uv"] = myProtonForwCut_1998_uv();
  ProtonCut["1999_d1"] = myProtonForwCut_1999_d1();
  ProtonCut["1999_d2"] = myProtonForwCut_1999_d2();
  ProtonCut["1999_uv"] = myProtonForwCut_1999_uv();
  ProtonCut["1999_vis"] = myProtonForwCut_1999_vis();
  ProtonCut["2000_fuv"] = myProtonForwCut_2000_fuv();
  ProtonCut["2000_uv1"] = myProtonForwCut_2000_uv1();
  ProtonCut["2000_uv2"] = myProtonForwCut_2000_uv2();
  ProtonCut["2000_vis"] = myProtonForwCut_2000_vis();
  ProtonCut["2001_d"] = myProtonForwCut_2001_d();
  ProtonCut["2001_uv"] = myProtonForwCut_2001_uv();
  ProtonCut["2002_d1"] = myProtonForwCut_2002_d1();
  ProtonCut["2002_d2"] = myProtonForwCut_2002_d2();
  ProtonCut["2002_d3"] = myProtonForwCut_2002_d3();
  ProtonCut["2002_uv1"] = myProtonForwCut_2002_uv1();
  ProtonCut["2002_uv2"] = myProtonForwCut_2002_uv2();
  ProtonCut["2002_vis1"] = myProtonForwCut_2002_vis1();
  ProtonCut["2002_vis2"] = myProtonForwCut_2002_vis2();
  ProtonCut["2003_vis"] = myProtonForwCut_2003_vis();
  ProtonCut["2005_d2"] = myProtonForwCut_2005_d2();
  ProtonCut["2006_d"] = myProtonForwCut_2006_d();

  return ProtonCut[cartella];
}

TCutG *myPionForwCut(){
  TCutG * PionForwCut = new TCutG("myPionForwCut",18);
  PionForwCut->SetVarX("");
  PionForwCut->SetVarY("");
  PionForwCut->SetNameTitle("PionForwCut");
  PionForwCut->SetFillStyle(1000);
  PionForwCut->SetPoint(0,8.89755,129.375);
  PionForwCut->SetPoint(1,9.1804,73.7298);
  PionForwCut->SetPoint(2,9.1804,73.7298);
  PionForwCut->SetPoint(3,9.70568,73.7298);
  PionForwCut->SetPoint(4,10.1906,73.7298);
  PionForwCut->SetPoint(5,10.5946,73.7298);
  PionForwCut->SetPoint(6,11.0391,80.6855);
  PionForwCut->SetPoint(7,11.5644,131.694);
  PionForwCut->SetPoint(8,11.5644,180.383);
  PionForwCut->SetPoint(9,11.5644,180.383);
  PionForwCut->SetPoint(10,10.8775,203.569);
  PionForwCut->SetPoint(11,10.8775,203.569);
  PionForwCut->SetPoint(12,9.74609,203.569);
  PionForwCut->SetPoint(13,9.2208,203.569);
  PionForwCut->SetPoint(14,8.97836,168.79);
  PionForwCut->SetPoint(15,8.97836,168.79);
  PionForwCut->SetPoint(16,8.97836,110.827);
  PionForwCut->SetPoint(17,8.89755,129.375);

  return PionForwCut;
}



TF1* CutDeuForw(string cartella){
 
  map<string,TF1*> DeuCut;
  DeuCut["2002_d1"] = ForwDeuFit_2002_d1();
  DeuCut["2002_d3"] = ForwDeuFit_2002_d3();
  DeuCut["2005_d2"] = ForwDeuFit_2005_d2();
  DeuCut["2006_d"] = ForwDeuFit_2006_d();
  
  
  return DeuCut[cartella];


}




