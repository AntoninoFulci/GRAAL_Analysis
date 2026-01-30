TCutG *myPionCentrCut_2003_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2003_vis",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0154728,8.09028);
   cutg->SetPoint(1,0.0348137,6.31076);
   cutg->SetPoint(2,0.0648997,4.79167);
   cutg->SetPoint(3,0.0971347,3.88021);
   cutg->SetPoint(4,0.159456,3.14236);
   cutg->SetPoint(5,0.208883,2.83854);
   cutg->SetPoint(6,0.208883,2.83854);
   cutg->SetPoint(7,0.292693,2.62153);
   cutg->SetPoint(8,0.290544,2.57812);
   cutg->SetPoint(9,0.294842,2.27431);
   cutg->SetPoint(10,0.29914,2.10069);
   cutg->SetPoint(11,0.292693,1.79687);
   cutg->SetPoint(12,0.29914,1.53646);
   cutg->SetPoint(13,0.213181,1.36285);
   cutg->SetPoint(14,0.0606017,1.79687);
   cutg->SetPoint(15,0.00902578,0.798611);
   cutg->SetPoint(16,0.00902578,8.09028);
   cutg->SetPoint(17,0.0154728,8.09028);
   cutg->SetPoint(18,0.0154728,8.09028);
   
   return cutg;
}
