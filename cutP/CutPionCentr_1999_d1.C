TCutG *myPionCentrCut_1999_d1(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_1999_d1",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0171944,8.08926);
   cutg->SetPoint(1,0.0361938,6.28063);
   cutg->SetPoint(2,0.0665928,4.76371);
   cutg->SetPoint(3,0.105731,3.57639);
   cutg->SetPoint(4,0.16159,3.1301);
   cutg->SetPoint(5,0.21533,3.09896);
   cutg->SetPoint(6,0.221776,3.01215);
   cutg->SetPoint(7,0.307736,2.70833);
   cutg->SetPoint(8,0.357163,2.62153);
   cutg->SetPoint(9,0.372206,2.36111);
   cutg->SetPoint(10,0.367908,2.40451);
   cutg->SetPoint(11,0.355014,1.71007);
   cutg->SetPoint(12,0.324928,1.62326);
   cutg->SetPoint(13,0.241117,1.62326);
   cutg->SetPoint(14,0.0477077,1.84028);
   cutg->SetPoint(15,0.0086447,1.02975);
   cutg->SetPoint(16,0.00959467,8.06009);
   cutg->SetPoint(17,0.0171944,8.08926);
   cutg->SetPoint(18,0.0171944,8.08926);
   
   return cutg;
}
