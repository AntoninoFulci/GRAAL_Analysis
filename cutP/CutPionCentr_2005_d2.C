TCutG *myPionCentrCut_2005_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
  
   TCutG *cutg = new TCutG("CUTCentrPion_2005_d2",23);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0154728,0.928819);
   cutg->SetPoint(1,0.0412607,1.05903);
   cutg->SetPoint(2,0.0541547,1.49306);
   cutg->SetPoint(3,0.0648997,1.97049);
   cutg->SetPoint(4,0.148711,1.44965);
   cutg->SetPoint(5,0.238968,1.44965);
   cutg->SetPoint(6,0.296991,1.53646);
   cutg->SetPoint(7,0.329226,1.88368);
   cutg->SetPoint(8,0.337822,2.1441);
   cutg->SetPoint(9,0.318481,2.57812);
   cutg->SetPoint(10,0.275647,2.65928);
   cutg->SetPoint(11,0.236853,2.83241);
   cutg->SetPoint(12,0.17046,3.36331);
   cutg->SetPoint(13,0.138414,3.86691);
   cutg->SetPoint(14,0.103903,4.19065);
   cutg->SetPoint(15,0.0477077,5.2691);
   cutg->SetPoint(16,0.0197708,6.00694);
   cutg->SetPoint(17,0.0197708,6.35417);
   cutg->SetPoint(18,0.0176218,4.53125);
   cutg->SetPoint(19,0.0133238,2.1441);
   cutg->SetPoint(20,0.0154728,0.755208);
   cutg->SetPoint(21,0.0154728,0.755208);
   cutg->SetPoint(22,0.0154728,0.928819);
   
   return cutg;
}
