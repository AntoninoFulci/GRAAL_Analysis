TCutG *myPionCentrCut_2000_uv2(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2000_uv2",18);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0154728,7.91667);
   cutg->SetPoint(1,0.0348137,6.13715);
   cutg->SetPoint(2,0.0648997,4.61806);
   cutg->SetPoint(3,0.0971347,3.7066);
   cutg->SetPoint(4,0.163754,3.35937);
   cutg->SetPoint(5,0.191691,3.18576);
   cutg->SetPoint(6,0.236819,2.96875);
   cutg->SetPoint(7,0.29914,2.66493);
   cutg->SetPoint(8,0.357163,2.57812);
   cutg->SetPoint(9,0.415186,2.27431);
   cutg->SetPoint(10,0.417335,1.44965);
   cutg->SetPoint(11,0.372206,1.44965);
   cutg->SetPoint(12,0.25616,1.44965);
   cutg->SetPoint(13,0.0520057,1.75347);
   cutg->SetPoint(14,0.00687678,0.885417);
   cutg->SetPoint(15,0.00902578,7.91667);
   cutg->SetPoint(16,0.0154728,7.91667);
   cutg->SetPoint(17,0.0154728,7.91667);
   
   return cutg;
}
