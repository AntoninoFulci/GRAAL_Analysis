TCutG *myProtonForwCut_2006_d(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2006_d",33);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,30.8363,57.9489);
   cutg->SetPoint(1,33.4314,44.5966);
   cutg->SetPoint(2,37.0188,33.4697);
   cutg->SetPoint(3,39.385,27.6837);
   cutg->SetPoint(4,42.2091,23.678);
   cutg->SetPoint(5,44.8042,17.892);
   cutg->SetPoint(6,48.2389,12.9962);
   cutg->SetPoint(7,51.2157,11.661);
   cutg->SetPoint(8,54.0398,7.6553);
   cutg->SetPoint(9,49.8418,6.76515);
   cutg->SetPoint(10,46.3308,8.54545);
   cutg->SetPoint(11,43.4303,11.661);
   cutg->SetPoint(12,40.2246,15.2216);
   cutg->SetPoint(13,37.5531,19.6723);
   cutg->SetPoint(14,34.6527,27.6837);
   cutg->SetPoint(15,32.6681,33.0246);
   cutg->SetPoint(16,31.5232,38.3655);
   cutg->SetPoint(17,30.302,32.5795);
   cutg->SetPoint(18,28.0122,24.5682);
   cutg->SetPoint(19,24.6538,15.6667);
   cutg->SetPoint(20,21.7533,10.7708);
   cutg->SetPoint(21,18.0133,7.21023);
   cutg->SetPoint(22,14.9602,5.875);
   cutg->SetPoint(23,13.7389,6.32007);
   cutg->SetPoint(24,13.5863,11.2159);
   cutg->SetPoint(25,18.2423,15.6667);
   cutg->SetPoint(26,22.9746,24.1231);
   cutg->SetPoint(27,26.8673,33.4697);
   cutg->SetPoint(28,28.7754,45.0417);
   cutg->SetPoint(29,30.073,55.2784);
   cutg->SetPoint(30,30.6836,58.839);
   cutg->SetPoint(31,30.9889,56.6136);
   cutg->SetPoint(32,30.8363,57.9489);

   return cutg;
}
