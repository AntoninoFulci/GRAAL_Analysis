TCutG *myPionCentrCut_2001_d(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2001_d",21);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0197708,8.4375);
   cutg->SetPoint(1,0.0391117,6.65799);
   cutg->SetPoint(2,0.0713467,5.09549);
   cutg->SetPoint(3,0.0992837,3.88021);
   cutg->SetPoint(4,0.176648,2.79514);
   cutg->SetPoint(5,0.217479,2.83854);
   cutg->SetPoint(6,0.236819,2.79514);
   cutg->SetPoint(7,0.301289,2.75174);
   cutg->SetPoint(8,0.314183,2.27431);
   cutg->SetPoint(9,0.316332,2.1441);
   cutg->SetPoint(10,0.318481,2.01389);
   cutg->SetPoint(11,0.314183,1.92708);
   cutg->SetPoint(12,0.29914,1.44965);
   cutg->SetPoint(13,0.221776,1.36285);
   cutg->SetPoint(14,0.155158,1.53646);
   cutg->SetPoint(15,0.118625,1.79687);
   cutg->SetPoint(16,0.0563037,2.27431);
   cutg->SetPoint(17,0.00902578,0.711805);
   cutg->SetPoint(18,0.0133238,8.4375);
   cutg->SetPoint(19,0.0197708,8.4375);
   cutg->SetPoint(20,0.0197708,8.4375);
   
   return cutg;
}
