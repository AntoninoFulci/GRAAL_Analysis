TCutG *myProtonCentrCut_2002_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2002_d2",28);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("De_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.109698,5.11773);
   cutg->SetPoint(1,0.0741379,6.74515);
   cutg->SetPoint(2,0.0515086,8.2687);
   cutg->SetPoint(3,0.0342672,9.93075);
   cutg->SetPoint(4,0.0278017,10.8657);
   cutg->SetPoint(5,0.0176218,13.1684);
   cutg->SetPoint(6,0.0176218,14.7743);
   cutg->SetPoint(7,0.0181034,16.1288);
   cutg->SetPoint(8,0.0154728,18.1597);
   cutg->SetPoint(9,0.0154728,20.1128);
   cutg->SetPoint(10,0.0434097,19.809);
   cutg->SetPoint(11,0.0461207,17.2022);
   cutg->SetPoint(12,0.0515086,15.1247);
   cutg->SetPoint(13,0.0606017,13.125);
   cutg->SetPoint(14,0.0863897,10.6076);
   cutg->SetPoint(15,0.114327,8.74132);
   cutg->SetPoint(16,0.157307,7.22222);
   cutg->SetPoint(17,0.212069,5.84488);
   cutg->SetPoint(18,0.255172,5.01385);
   cutg->SetPoint(19,0.275647,4.39058);
   cutg->SetPoint(20,0.286246,4.18403);
   cutg->SetPoint(21,0.301289,3.83681);
   cutg->SetPoint(22,0.327077,2.88194);
   cutg->SetPoint(23,0.260458,2.92535);
   cutg->SetPoint(24,0.219628,2.96875);
   cutg->SetPoint(25,0.170201,3.31597);
   cutg->SetPoint(26,0.128017,4.18283);
   cutg->SetPoint(27,0.109698,5.11773);
   
   return cutg;
}
