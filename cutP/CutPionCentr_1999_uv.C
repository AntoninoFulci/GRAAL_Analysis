TCutG *myPionCentrCut_1999_uv(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_1999_uv",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.00687678,7.78646);
   cutg->SetPoint(1,0.0434097,5.44271);
   cutg->SetPoint(2,0.0648997,4.79167);
   cutg->SetPoint(3,0.116476,3.7934);
   cutg->SetPoint(4,0.159456,3.14236);
   cutg->SetPoint(5,0.202436,3.01215);
   cutg->SetPoint(6,0.21533,3.05556);
   cutg->SetPoint(7,0.29914,2.83854);
   cutg->SetPoint(8,0.357163,2.75174);
   cutg->SetPoint(9,0.443123,2.62153);
   cutg->SetPoint(10,0.473209,2.44792);
   cutg->SetPoint(11,0.503295,2.27431);
   cutg->SetPoint(12,0.498997,1.57986);
   cutg->SetPoint(13,0.213181,1.36285);
   cutg->SetPoint(14,0.0648997,1.62326);
   cutg->SetPoint(15,0.0133238,0.928819);
   cutg->SetPoint(16,0.00902578,8.09028);
   cutg->SetPoint(17,0.00687678,7.82986);
   cutg->SetPoint(18,0.00687678,7.78646);
   
   return cutg;
}
