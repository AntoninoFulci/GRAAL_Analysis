TCutG *myPionCentrCut_2002_d3(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
  
   TCutG *cutg = new TCutG("CUTCentrPion_2003_d3",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0283668,8.09028);
   cutg->SetPoint(1,0.0361938,6.28063);
   cutg->SetPoint(2,0.0665928,4.76371);
   cutg->SetPoint(3,0.0885387,3.92361);
   cutg->SetPoint(4,0.16159,3.1301);
   cutg->SetPoint(5,0.210038,2.83839);
   cutg->SetPoint(6,0.210038,2.83839);
   cutg->SetPoint(7,0.299335,2.83839);
   cutg->SetPoint(8,0.359183,2.7217);
   cutg->SetPoint(9,0.402292,2.49132);
   cutg->SetPoint(10,0.425931,2.1875);
   cutg->SetPoint(11,0.432378,1.88368);
   cutg->SetPoint(12,0.415186,1.49306);
   cutg->SetPoint(13,0.214788,1.32147);
   cutg->SetPoint(14,0.0563037,1.71007);
   cutg->SetPoint(15,0.0086447,1.02975);
   cutg->SetPoint(16,0.00959467,8.06009);
   cutg->SetPoint(17,0.0133238,7.96007);
   cutg->SetPoint(18,0.0283668,8.09028);
   
   return cutg;
}
