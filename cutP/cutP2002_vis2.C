TCutG *myProtonForwCut_2002_vis2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CUTG",34);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,12.0559,12.4369);
   cutg->SetPoint(1,14.7762,18.1571);
   cutg->SetPoint(2,17.8057,24.0619);
   cutg->SetPoint(3,21.0206,30.8893);
   cutg->SetPoint(4,23.1226,36.9786);
   cutg->SetPoint(5,25.9048,45.2821);
   cutg->SetPoint(6,27.5122,56.7226);
   cutg->SetPoint(7,28.0068,59.8595);
   cutg->SetPoint(8,28.3778,62.0738);
   cutg->SetPoint(9,28.8106,62.9964);
   cutg->SetPoint(10,31.2217,54.5083);
   cutg->SetPoint(11,33.1383,47.3119);
   cutg->SetPoint(12,37.6516,32.919);
   cutg->SetPoint(13,40.7428,26.2762);
   cutg->SetPoint(14,46.1834,18.3417);
   cutg->SetPoint(15,50.1403,13.544);
   cutg->SetPoint(16,51.7477,11.3298);
   cutg->SetPoint(17,45.5652,10.9607);
   cutg->SetPoint(18,42.7212,13.544);
   cutg->SetPoint(19,42.4739,14.2821);
   cutg->SetPoint(20,37.9607,22.0321);
   cutg->SetPoint(21,35.0549,28.306);
   cutg->SetPoint(22,33.8802,31.9964);
   cutg->SetPoint(23,33.5711,32.919);
   cutg->SetPoint(24,33.5711,32.919);
   cutg->SetPoint(25,30.1707,45.0976);
   cutg->SetPoint(26,29.4288,47.681);
   cutg->SetPoint(27,28.1305,38.4548);
   cutg->SetPoint(28,24.7919,27.7524);
   cutg->SetPoint(29,20.2787,17.2345);
   cutg->SetPoint(30,17.2492,12.9905);
   cutg->SetPoint(31,12.4269,5.79405);
   cutg->SetPoint(32,11.9941,10.7762);
   cutg->SetPoint(33,12.0559,12.4369);

   return cutg;
}
