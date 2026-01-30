TCutG *myProtonForwCut_1999_d1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_1999_d1",32);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("dE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,29.5487,68.0511);
   cutg->SetPoint(1,31.2909,58.1648);
   cutg->SetPoint(2,34.1482,46.2187);
   cutg->SetPoint(3,38.1903,32.625);
   cutg->SetPoint(4,40.3507,26.446);
   cutg->SetPoint(5,45.6471,16.9716);
   cutg->SetPoint(6,49.2013,12.4403);
   cutg->SetPoint(7,46.2743,10.7926);
   cutg->SetPoint(8,42.302,14.5);
   cutg->SetPoint(9,39.7931,18.2074);
   cutg->SetPoint(10,37.8418,21.0909);
   cutg->SetPoint(11,35.4027,28.0937);
   cutg->SetPoint(12,32.9635,35.9205);
   cutg->SetPoint(13,31.5697,41.6875);
   cutg->SetPoint(14,30.594,44.571);
   cutg->SetPoint(15,29.6881,49.5142);
   cutg->SetPoint(16,28.7821,44.571);
   cutg->SetPoint(17,26.7611,35.0966);
   cutg->SetPoint(18,24.1825,26.0341);
   cutg->SetPoint(19,22.1615,21.9148);
   cutg->SetPoint(20,20.0708,15.7358);
   cutg->SetPoint(21,15.8894,9.96875);
   cutg->SetPoint(22,13.7987,7.90909);
   cutg->SetPoint(23,12.5442,7.90909);
   cutg->SetPoint(24,12.4746,11.6165);
   cutg->SetPoint(25,15.8894,18.6193);
   cutg->SetPoint(26,20.0708,26.446);
   cutg->SetPoint(27,23.2765,35.9205);
   cutg->SetPoint(28,26.4126,49.9261);
   cutg->SetPoint(29,28.5033,59.4006);
   cutg->SetPoint(30,29.5487,66.8153);
   cutg->SetPoint(31,29.5487,68.0511);

   return cutg;
}
