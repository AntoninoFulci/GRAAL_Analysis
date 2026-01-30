TCutG *myProtonCentrCut_2000_fuv(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2000_fuv",20);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.163754,4.44444);
   cutg->SetPoint(1,0.118625,5.87674);
   cutg->SetPoint(2,0.0799427,7.78646);
   cutg->SetPoint(3,0.0520057,9.52257);
   cutg->SetPoint(4,0.0262178,11.6059);
   cutg->SetPoint(5,0.0176218,14.0365);
   cutg->SetPoint(6,0.00902578,17.3351);
   cutg->SetPoint(7,0.0133238,19.9392);
   cutg->SetPoint(8,0.0434097,19.9392);
   cutg->SetPoint(9,0.0477077,17.1181);
   cutg->SetPoint(10,0.0520057,13.9497);
   cutg->SetPoint(11,0.0777937,11.3021);
   cutg->SetPoint(12,0.114327,8.82812);
   cutg->SetPoint(13,0.163754,7.17882);
   cutg->SetPoint(14,0.249713,4.96528);
   cutg->SetPoint(15,0.284097,4.27083);
   cutg->SetPoint(16,0.279799,3.40278);
   cutg->SetPoint(17,0.19384,3.35937);
   cutg->SetPoint(18,0.161605,4.44444);
   cutg->SetPoint(19,0.163754,4.44444);
   
   return cutg;
}
