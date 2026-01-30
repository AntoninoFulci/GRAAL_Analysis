TCutG *myPionCentrCut_2000_vis(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2000_vis",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0336483,7.6551);
   cutg->SetPoint(1,0.0509039,6.3257);
   cutg->SetPoint(2,0.0656943,3.99926);
   cutg->SetPoint(3,0.156902,3.40842);
   cutg->SetPoint(4,0.17539,3.18685);
   cutg->SetPoint(5,0.224692,2.89143);
   cutg->SetPoint(6,0.224692,2.89143);
   cutg->SetPoint(7,0.267831,2.66987);
   cutg->SetPoint(8,0.280156,2.33752);
   cutg->SetPoint(9,0.282621,2.15288);
   cutg->SetPoint(10,0.276458,1.85746);
   cutg->SetPoint(11,0.269063,1.48818);
   cutg->SetPoint(12,0.246878,1.3774);
   cutg->SetPoint(13,0.228389,1.3774);
   cutg->SetPoint(14,0.0656943,2.07902);
   cutg->SetPoint(15,0.0176253,0.934269);
   cutg->SetPoint(16,0.0114626,7.43353);
   cutg->SetPoint(17,0.0213229,7.83973);
   cutg->SetPoint(18,0.0336483,7.6551);
   
   return cutg;
}
