TCutG* ProtonCntCut_1999_d2(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06

  TCutG *cutg = new TCutG("ProtonCntCut_1999_d2",24);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.12937,5.61632);
   cutg->SetPoint(1,0.105731,6.26736);
   cutg->SetPoint(2,0.0842407,7.17882);
   cutg->SetPoint(3,0.0627507,8.65451);
   cutg->SetPoint(4,0.0477077,10.2604);
   cutg->SetPoint(5,0.0369627,11.4757);
   cutg->SetPoint(6,0.0283668,13.342);
   cutg->SetPoint(7,0.0176218,14.5573);
   cutg->SetPoint(8,0.0176218,16.467);
   cutg->SetPoint(9,0.0154728,18.6372);
   cutg->SetPoint(10,0.0326647,18.6372);
   cutg->SetPoint(11,0.0584527,13.8628);
   cutg->SetPoint(12,0.0691977,12.3003);
   cutg->SetPoint(13,0.101433,10.0434);
   cutg->SetPoint(14,0.140115,8.17708);
   cutg->SetPoint(15,0.155158,7.43924);
   cutg->SetPoint(16,0.245415,5.74653);
   cutg->SetPoint(17,0.301289,4.27083);
   cutg->SetPoint(18,0.305587,3.83681);
   cutg->SetPoint(19,0.281948,3.53299);
   cutg->SetPoint(20,0.238968,3.40278);
   cutg->SetPoint(21,0.206734,3.96701);
   cutg->SetPoint(22,0.165903,4.74826);
   cutg->SetPoint(23,0.12937,5.61632);

   return cutg;
}
