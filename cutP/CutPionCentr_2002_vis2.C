TCutG *myPionCentrCut_2002_vis2(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2002_vis2",18);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0171944,8.08926);
   cutg->SetPoint(1,0.0361938,6.28063);
   cutg->SetPoint(2,0.0665928,4.76371);
   cutg->SetPoint(3,0.0979417,3.85939);
   cutg->SetPoint(4,0.16159,3.1301);
   cutg->SetPoint(5,0.210038,2.83839);
   cutg->SetPoint(6,0.210038,2.83839);
   cutg->SetPoint(7,0.279799,2.70833);
   cutg->SetPoint(8,0.344269,2.27431);
   cutg->SetPoint(9,0.352865,1.75347);
   cutg->SetPoint(10,0.331375,1.57986);
   cutg->SetPoint(11,0.305587,1.53646);
   cutg->SetPoint(12,0.120774,1.75347);
   cutg->SetPoint(13,0.0734957,1.84028);
   cutg->SetPoint(14,0.0086447,1.02975);
   cutg->SetPoint(15,0.00959467,8.06009);
   cutg->SetPoint(16,0.0171944,8.08926);
   cutg->SetPoint(17,0.0171944,8.08926);
   
   return cutg;
}
