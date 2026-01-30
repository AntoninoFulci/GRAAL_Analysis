TCutG *myPionCentrCut_2002_uv2(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2002_uv2",18);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,-0.0038682,8.13368);
   cutg->SetPoint(1,0.0361938,6.28063);
   cutg->SetPoint(2,0.0665928,4.76371);
   cutg->SetPoint(3,0.0885387,3.92361);
   cutg->SetPoint(4,0.16159,3.1301);
   cutg->SetPoint(5,0.210038,2.83839);
   cutg->SetPoint(6,0.210038,2.83839);
   cutg->SetPoint(7,0.299335,2.83839);
   cutg->SetPoint(8,0.359183,2.7217);
   cutg->SetPoint(9,0.42808,2.57812);
   cutg->SetPoint(10,0.447421,2.27431);
   cutg->SetPoint(11,0.432378,1.88368);
   cutg->SetPoint(12,0.415186,1.49306);
   cutg->SetPoint(13,0.214788,1.32147);
   cutg->SetPoint(14,0.0086447,1.02975);
   cutg->SetPoint(15,0.00959467,8.06009);
   cutg->SetPoint(16,-0.00171921,8.26389);
   cutg->SetPoint(17,-0.0038682,8.13368);
   
   return cutg;
}
