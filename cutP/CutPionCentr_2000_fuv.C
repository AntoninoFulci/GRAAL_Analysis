TCutG *myPionCentrCut_2000_fuv(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2000_fuv",19);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0170259,8.09557);
   cutg->SetPoint(1,0.0353448,6.29501);
   cutg->SetPoint(2,0.0541547,4.74826);
   cutg->SetPoint(3,0.0648997,3.7934);
   cutg->SetPoint(4,0.0885387,3.35937);
   cutg->SetPoint(5,0.112178,3.01215);
   cutg->SetPoint(6,0.178797,2.79514);
   cutg->SetPoint(7,0.284097,2.79514);
   cutg->SetPoint(8,0.314183,2.40451);
   cutg->SetPoint(9,0.309885,1.97049);
   cutg->SetPoint(10,0.316332,1.79687);
   cutg->SetPoint(11,0.301289,1.62326);
   cutg->SetPoint(12,0.245415,1.62326);
   cutg->SetPoint(13,0.142264,1.62326);
   cutg->SetPoint(14,0.0584527,1.97049);
   cutg->SetPoint(15,0.00840516,1.03186);
   cutg->SetPoint(16,0.00948275,8.06094);
   cutg->SetPoint(17,0.0170259,8.09557);
   cutg->SetPoint(18,0.0170259,8.09557);
   
   return cutg;
}
