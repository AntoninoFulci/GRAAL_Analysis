TCutG *myPionCentrCut_2001_uv(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CUTCentrPion_2001_uv",24);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0391117,6.13715);
   cutg->SetPoint(1,0.0369627,6.31076);
   cutg->SetPoint(2,0.0563037,4.87847);
   cutg->SetPoint(3,0.0799427,3.18576);
   cutg->SetPoint(4,0.146562,2.92535);
   cutg->SetPoint(5,0.208883,2.88194);
   cutg->SetPoint(6,0.208883,2.88194);
   cutg->SetPoint(7,0.296991,2.88194);
   cutg->SetPoint(8,0.309885,2.75174);
   cutg->SetPoint(9,0.318481,2.53472);
   cutg->SetPoint(10,0.331375,2.2309);
   cutg->SetPoint(11,0.327077,1.79687);
   cutg->SetPoint(12,0.312034,1.44965);
   cutg->SetPoint(13,0.21533,1.40625);
   cutg->SetPoint(14,0.118625,1.49306);
   cutg->SetPoint(15,0.0563037,1.92708);
   cutg->SetPoint(16,0.00902578,1.10243);
   cutg->SetPoint(17,0.00902578,8.13368);
   cutg->SetPoint(18,-0.0124642,8.04687);
   cutg->SetPoint(19,0.0176218,7.09201);
   cutg->SetPoint(20,0.0434097,6.00694);
   cutg->SetPoint(21,0.0412607,5.96354);
   cutg->SetPoint(22,0.0369627,6.18056);
   cutg->SetPoint(23,0.0391117,6.13715);
   
   return cutg;
}
