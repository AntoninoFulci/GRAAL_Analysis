/////////////////////////////////////////////////////////
// File contente i cut utilizzati nel l'algorimo
// di progessing dei dati
///////////////////////////////////////////////////
#include "TCutG.h"
#include "cutP/CutPionCentr_1998_uv.C"
#include "cutP/CutPionCentr_1999_uv.C"
#include "cutP/CutPionCentr_1999_d1.C"
#include "cutP/CutPionCentr_1999_d2.C"
#include "cutP/CutPionCentr_1999_vis.C"
#include "cutP/CutPionCentr_2000_fuv.C"
#include "cutP/CutPionCentr_2000_uv1.C"
#include "cutP/CutPionCentr_2000_uv2.C"
#include "cutP/CutPionCentr_2000_vis.C"
#include "cutP/CutPionCentr_2001_d.C"
#include "cutP/CutPionCentr_2001_uv.C"
#include "cutP/CutPionCentr_2002_d1.C"
#include "cutP/CutPionCentr_2002_d2.C"
#include "cutP/CutPionCentr_2002_d3.C"
#include "cutP/CutPionCentr_2002_uv1.C"
#include "cutP/CutPionCentr_2002_uv2.C"
#include "cutP/CutPionCentr_2002_vis1.C"
#include "cutP/CutPionCentr_2002_vis2.C"
#include "cutP/CutPionCentr_2003_vis.C"
#include "cutP/CutPionCentr_2005_d1.C"
#include "cutP/CutPionCentr_2005_d2.C"
#include "cutP/CutPionCentr_2006_d.C"
#include "cutP/CutProCentr_1998_uv.C"
#include "cutP/CutProCentr_1999_uv.C"
#include "cutP/CutProCentr_1999_d1.C"
#include "cutP/CutProCentr_1999_d2.C"
#include "cutP/CutProCentr_1999_vis.C"
#include "cutP/CutProCentr_2000_fuv.C"
#include "cutP/CutProCentr_2000_uv1.C"
#include "cutP/CutProCentr_2000_uv2.C"
#include "cutP/CutProCentr_2000_vis.C"
#include "cutP/CutProCentr_2001_d.C"
#include "cutP/CutProCentr_2001_uv.C"
#include "cutP/CutProCentr_2002_d1.C"
#include "cutP/CutProCentr_2002_d2.C"
#include "cutP/CutProCentr_2002_d3.C"
#include "cutP/CutProCentr_2002_uv1.C"
#include "cutP/CutProCentr_2002_uv2.C"
#include "cutP/CutProCentr_2002_vis1.C"
#include "cutP/CutProCentr_2002_vis2.C"
#include "cutP/CutProCentr_2003_vis.C"
#include "cutP/CutProCentr_2005_d1.C"
#include "cutP/CutProCentr_2005_d2.C"
#include "cutP/CutProCentr_2006_d.C"
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
#include "cutP/cutP2002_d1.C"
#include "cutP/cutP2002_d1_test.C"
#include "cutP/cutP2002_d2.C"
#include "cutP/cutP2002_d3.C"
#include "cutP/cutP2002_d3_test.C"
#include "cutP/cutP2002_uv1.C"
#include "cutP/cutP2002_uv2.C"
#include "cutP/cutP2002_vis1.C"
#include "cutP/cutP2002_vis2.C"
#include "cutP/cutP2003_vis.C"
#include "cutP/cutP2005_d2.C"
#include "cutP/cutP2005_d2_test.C"
#include "cutP/cutP2006_d.C"
#include "cutP/cutP2006_d_test.C"
#include "cutP/CutPionForw_1998_uv.C"
#include "cutP/CutPionForw_1999_uv.C"
#include "cutP/CutPionForw_1999_d1.C"
#include "cutP/CutPionForw_1999_d2.C"
#include "cutP/CutPionForw_1999_vis.C"
#include "cutP/CutPionForw_2000_vis.C"
#include "cutP/CutPionForw_2000_fuv.C"
#include "cutP/CutPionForw_2000_uv1.C"
#include "cutP/CutPionForw_2000_uv2.C"
#include "cutP/CutPionForw_2001_d.C"
#include "cutP/CutPionForw_2001_uv.C"
#include "cutP/CutPionForw_2002_d1.C"
#include "cutP/CutPionForw_2002_d2.C"
#include "cutP/CutPionForw_2002_d3.C"
#include "cutP/CutPionForw_2002_uv1.C"
#include "cutP/CutPionForw_2002_uv2.C"
#include "cutP/CutPionForw_2002_vis1.C"
#include "cutP/CutPionForw_2002_vis2.C"
#include "cutP/CutPionForw_2003_vis.C"
#include "cutP/CutPionForw_2005_d1.C"
#include "cutP/CutPionForw_2005_d2.C"
#include "cutP/CutPionForw_2006_d.C"
#include "cutP/CutDeuForw_1999_d1.C"
#include "cutP/CutDeuForw_1999_d2.C"
#include "cutP/CutDeuForw_2001_d.C"
#include "cutP/CutDeuForw_2002_d1.C"
#include "cutP/CutDeuForw_2002_d2.C"
#include "cutP/CutDeuForw_2002_d3.C"
#include "cutP/CutDeuForw_2005_d2.C"
#include "cutP/CutDeuForw_2006_d.C"



TCutG *myProtonCentrCut(string cartella){

   map<string, TCutG*> ProtonCentrCut;
   ProtonCentrCut["1998_uv"] = myProtonCentrCut_1998_uv();
   ProtonCentrCut["1999_uv"] = myProtonCentrCut_1999_uv();
   ProtonCentrCut["1999_vis"] = myProtonCentrCut_1999_vis();
   ProtonCentrCut["1999_d1"] = myProtonCentrCut_1999_d1();
   ProtonCentrCut["1999_d2"] = myProtonCentrCut_1999_d2();
   ProtonCentrCut["2000_fuv"] = myProtonCentrCut_2000_fuv();
   ProtonCentrCut["2000_uv1"] = myProtonCentrCut_2000_uv1();
   ProtonCentrCut["2000_uv2"] = myProtonCentrCut_2000_uv2();
   ProtonCentrCut["2000_vis"] = myProtonCentrCut_2000_vis();
   ProtonCentrCut["2001_d"] = myProtonCentrCut_2001_d();
   ProtonCentrCut["2001_uv"] = myProtonCentrCut_2001_uv();
   ProtonCentrCut["2002_d1"] = myProtonCentrCut_2002_d1();
   ProtonCentrCut["2002_d2"] = myProtonCentrCut_2002_d2();
   ProtonCentrCut["2002_d3"] = myProtonCentrCut_2002_d3();
   ProtonCentrCut["2002_uv1"] = myProtonCentrCut_2002_uv1();
   ProtonCentrCut["2002_uv2"] = myProtonCentrCut_2002_uv2();
   ProtonCentrCut["2002_vis1"] = myProtonCentrCut_2002_vis1();
   ProtonCentrCut["2002_vis2"] = myProtonCentrCut_2002_vis2();
   ProtonCentrCut["2003_vis"] = myProtonCentrCut_2003_vis();
   ProtonCentrCut["2005_d1"] = myProtonCentrCut_2005_d1();
   ProtonCentrCut["2005_d2"] = myProtonCentrCut_2005_d2();
   ProtonCentrCut["2006_d"] = myProtonCentrCut_2006_d();


   return ProtonCentrCut[cartella];
}

TCutG *myPionCentrCut(string cartella){

  map<string,TCutG*> PionCentrCut;
  PionCentrCut["1998_uv"] = myPionCentrCut_1998_uv();
  PionCentrCut["1999_uv"] = myPionCentrCut_1999_uv();
  PionCentrCut["1999_d1"] = myPionCentrCut_1999_d1();
  PionCentrCut["1999_d2"] = myPionCentrCut_1999_d2();
  PionCentrCut["1999_vis"] = myPionCentrCut_1999_vis();
  PionCentrCut["2000_fuv"] = myPionCentrCut_2000_fuv();
  PionCentrCut["2000_uv1"] = myPionCentrCut_2000_uv1();
  PionCentrCut["2000_uv2"] = myPionCentrCut_2000_uv2();
  PionCentrCut["2000_vis"] = myPionCentrCut_2000_vis();
  PionCentrCut["2001_d"] = myPionCentrCut_2001_d();
  PionCentrCut["2001_uv"] = myPionCentrCut_2001_uv();
  PionCentrCut["2002_d1"] = myPionCentrCut_2002_d1();
  PionCentrCut["2002_d2"] = myPionCentrCut_2002_d2();
  PionCentrCut["2002_d3"] = myPionCentrCut_2002_d2();
  PionCentrCut["2002_uv1"] = myPionCentrCut_2002_uv1();
  PionCentrCut["2002_uv2"] = myPionCentrCut_2002_uv2();
  PionCentrCut["2002_vis1"] = myPionCentrCut_2002_vis1();
  PionCentrCut["2002_vis2"] = myPionCentrCut_2002_vis2();
  PionCentrCut["2003_vis"] = myPionCentrCut_2003_vis();
  PionCentrCut["2005_d1"] = myPionCentrCut_2005_d1();
  PionCentrCut["2005_d2"] = myPionCentrCut_2005_d2();
  PionCentrCut["2006_d"] = myPionCentrCut_2006_d();

  return PionCentrCut[cartella];

}

TCutG *myProtonForwCut(string cartella){
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
  //ProtonCut["2002_d1"] = myProtonForwCut_2002_d1_test();
  ProtonCut["2002_d2"] = myProtonForwCut_2002_d2();
  ProtonCut["2002_d3"] = myProtonForwCut_2002_d3();
  //ProtonCut["2002_d3"] = myProtonForwCut_2002_d3_test();
  ProtonCut["2002_uv1"] = myProtonForwCut_2002_uv1();
  ProtonCut["2002_uv2"] = myProtonForwCut_2002_uv2();
  ProtonCut["2002_vis1"] = myProtonForwCut_2002_vis1();
  ProtonCut["2002_vis2"] = myProtonForwCut_2002_vis2();
  ProtonCut["2003_vis"] = myProtonForwCut_2003_vis();
  //ProtonCut["2005_d1"] = myProtonForwCut_2005_d1();
  ProtonCut["2005_d2"] = myProtonForwCut_2005_d2();
  //ProtonCut["2005_d2"] = myProtonForwCut_2005_d2_test();
  ProtonCut["2006_d"] = myProtonForwCut_2006_d();
  //ProtonCut["2006_d"] = myProtonForwCut_2006_d_test();
  return ProtonCut[cartella];
}

TCutG *myPionForwCut(string cartella){

  map<string, TCutG*> PionCut;
  PionCut["1998_uv"] = myPionForwCut_1998_uv();
  PionCut["1999_uv"] = myPionForwCut_1999_uv();
  PionCut["1999_d1"] = myPionForwCut_1999_d1();
  PionCut["1999_vis"] = myPionForwCut_1999_vis();
  PionCut["1999_d2"] = myPionForwCut_1999_d2();
  PionCut["2000_vis"] = myPionForwCut_2000_vis();
  PionCut["2000_fuv"] = myPionForwCut_2000_fuv();
  PionCut["2000_uv1"] = myPionForwCut_2000_uv1();
  PionCut["2000_uv2"] = myPionForwCut_2000_uv2();
  PionCut["2001_d"] = myPionForwCut_2001_d();
  PionCut["2001_uv"] = myPionForwCut_2001_uv();
  PionCut["2002_uv1"] = myPionForwCut_2002_uv1();
  PionCut["2002_d1"] = myPionForwCut_2002_d1();
  PionCut["2002_d2"] = myPionForwCut_2002_d2();
  PionCut["2002_d3"] = myPionForwCut_2002_d3();
  PionCut["2002_uv2"] = myPionForwCut_2002_uv2();
  PionCut["2002_vis1"] = myPionForwCut_2002_vis1();
  PionCut["2002_vis2"] = myPionForwCut_2002_vis2();
  PionCut["2003_vis"] = myPionForwCut_2003_vis();
  PionCut["2005_d1"] = myPionForwCut_2005_d1();
  PionCut["2005_d2"] = myPionForwCut_2005_d2();
  PionCut["2006_d"] = myPionForwCut_2006_d();


  return PionCut[cartella];


}

TCutG* myDeuForwCut(string cartella){
  map<string,TCutG*> DeuCut;

  DeuCut["1999_d1"] = myDeuForwCut_1999_d1();
  DeuCut["1999_d2"] = myDeuForwCut_1999_d2();
  DeuCut["2001_d"] = myDeuForwCut_2001_d();
  DeuCut["2002_d1"] = myDeuForwCut_2002_d1();
  DeuCut["2002_d2"] = myDeuForwCut_2002_d2();
  DeuCut["2002_d3"] = myDeuForwCut_2002_d3();
  DeuCut["2005_d2"] = myDeuForwCut_2005_d2();
  DeuCut["2006_d"] = myDeuForwCut_2006_d();

  return DeuCut[cartella];
}
