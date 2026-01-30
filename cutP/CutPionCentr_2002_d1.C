TCutG * myPionCentrCut_2002_d1(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2002_d1",18);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0176218,8.00347);
   cutg->SetPoint(1,0.0369627,6.22396);
   cutg->SetPoint(2,0.0670487,4.70486);
   cutg->SetPoint(3,0.120774,3.92361);
   cutg->SetPoint(4,0.168052,3.44618);
   cutg->SetPoint(5,0.19384,3.22917);
   cutg->SetPoint(6,0.219628,3.05556);
   cutg->SetPoint(7,0.301289,2.75174);
   cutg->SetPoint(8,0.359312,2.66493);
   cutg->SetPoint(9,0.447421,2.70833);
   cutg->SetPoint(10,0.498997,2.1441);
   cutg->SetPoint(11,0.498997,2.1441);
   cutg->SetPoint(12,0.501146,1.49306);
   cutg->SetPoint(13,0.21533,1.27604);
   cutg->SetPoint(14,0.00902578,0.972222);
   cutg->SetPoint(15,0.0111748,8.00347);
   cutg->SetPoint(16,0.0176218,8.00347);
   cutg->SetPoint(17,0.0176218,8.00347);
   
   return cutg;
}
