TCutG *myPionCentrCut_1999_d2(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_1999_d2",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0305158,7.26562);
   cutg->SetPoint(1,0.0412607,6.39757);
   cutg->SetPoint(2,0.0885387,4.22743);
   cutg->SetPoint(3,0.142264,3.61979);
   cutg->SetPoint(4,0.191691,3.27257);
   cutg->SetPoint(5,0.228223,3.05556);
   cutg->SetPoint(6,0.254011,2.88194);
   cutg->SetPoint(7,0.305587,2.92535);
   cutg->SetPoint(8,0.36361,2.83854);
   cutg->SetPoint(9,0.447421,2.57812);
   cutg->SetPoint(10,0.456017,2.1875);
   cutg->SetPoint(11,0.453868,1.92708);
   cutg->SetPoint(12,0.451719,1.57986);
   cutg->SetPoint(13,0.219628,1.44965);
   cutg->SetPoint(14,0.0627507,1.75347);
   cutg->SetPoint(15,0.0133238,1.14583);
   cutg->SetPoint(16,0.0154728,8.17708);
   cutg->SetPoint(17,0.0283668,7.65625);
   cutg->SetPoint(18,0.0305158,7.26562);
   
   return cutg;
}
