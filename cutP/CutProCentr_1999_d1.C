TCutG *myProtonCentrCut_1999_d1(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_1999_d1",34);
   cutg->SetVarX("Eclusc");
   cutg->SetVarY("Dedx");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetLineColor(2);
   cutg->SetPoint(0,0.0133238,11.7795);
   cutg->SetPoint(1,0.0111748,13.6024);
   cutg->SetPoint(2,0.0154728,14.3837);
   cutg->SetPoint(3,0.0133238,15.2517);
   cutg->SetPoint(4,0.0133238,16.3802);
   cutg->SetPoint(5,0.0154728,20.0694);
   cutg->SetPoint(6,0.0326647,19.9826);
   cutg->SetPoint(7,0.0498567,14.6007);
   cutg->SetPoint(8,0.0498567,13.8628);
   cutg->SetPoint(9,0.0648997,11.4757);
   cutg->SetPoint(10,0.0971347,9.08854);
   cutg->SetPoint(11,0.15086,7.43924);
   cutg->SetPoint(12,0.17235,6.70139);
   cutg->SetPoint(13,0.226074,5.57292);
   cutg->SetPoint(14,0.269054,4.96528);
   cutg->SetPoint(15,0.318481,4.61806);
   cutg->SetPoint(16,0.378653,4.01042);
   cutg->SetPoint(17,0.40659,3.61979);
   cutg->SetPoint(18,0.415186,3.22917);
   cutg->SetPoint(19,0.417335,2.92535);
   cutg->SetPoint(20,0.408739,2.75174);
   cutg->SetPoint(21,0.382951,2.66493);
   cutg->SetPoint(22,0.374355,2.66493);
   cutg->SetPoint(23,0.335673,3.01215);
   cutg->SetPoint(24,0.25616,3.18576);
   cutg->SetPoint(25,0.21533,3.44618);
   cutg->SetPoint(26,0.189542,3.66319);
   cutg->SetPoint(27,0.148711,4.40104);
   cutg->SetPoint(28,0.105731,5.57292);
   cutg->SetPoint(29,0.0799427,6.22396);
   cutg->SetPoint(30,0.0691977,6.96181);
   cutg->SetPoint(31,0.0412607,7.91667);
   cutg->SetPoint(32,0.0240688,9.56597);
   cutg->SetPoint(33,0.0133238,11.7795);
   
   return cutg;
}
