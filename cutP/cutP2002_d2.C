TCutG *myProtonForwCut_2002_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2002_d2",30);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,13.021,14.2661);
   cutg->SetPoint(1,13.6327,5.55398);
   cutg->SetPoint(2,16.6914,9.91004);
   cutg->SetPoint(3,20.7987,18.0777);
   cutg->SetPoint(4,24.0321,21.8892);
   cutg->SetPoint(5,26.5664,33.8684);
   cutg->SetPoint(6,28.2268,44.214);
   cutg->SetPoint(7,29.1007,49.1146);
   cutg->SetPoint(8,31.4602,36.0464);
   cutg->SetPoint(9,34.6062,27.3343);
   cutg->SetPoint(10,37.1405,20.8002);
   cutg->SetPoint(11,40.1117,13.1771);
   cutg->SetPoint(12,47.1029,6.09848);
   cutg->SetPoint(13,49.0254,12.6326);
   cutg->SetPoint(14,45.2677,15.8996);
   cutg->SetPoint(15,42.5586,22.4337);
   cutg->SetPoint(16,39.2378,29.5123);
   cutg->SetPoint(17,36.7035,37.1354);
   cutg->SetPoint(18,33.2954,46.392);
   cutg->SetPoint(19,31.1106,57.8267);
   cutg->SetPoint(20,29.7998,65.4498);
   cutg->SetPoint(21,28.052,63.2718);
   cutg->SetPoint(22,26.479,51.8371);
   cutg->SetPoint(23,24.469,39.3134);
   cutg->SetPoint(24,21.4104,28.9678);
   cutg->SetPoint(25,17.8274,24.0672);
   cutg->SetPoint(26,15.2058,19.7112);
   cutg->SetPoint(27,12.7588,13.7216);
   cutg->SetPoint(28,12.7588,13.7216);
   cutg->SetPoint(29,13.021,14.2661);

   return cutg;
}
