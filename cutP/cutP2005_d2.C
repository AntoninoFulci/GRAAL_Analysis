TCutG *myProtonForwCut_2005_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2005_d2",36);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.8407,4.49148);
   cutg->SetPoint(1,11.8407,10.6562);
   cutg->SetPoint(2,13.8119,12.858);
   cutg->SetPoint(3,17.2765,15.5);
   cutg->SetPoint(4,20.1438,22.5455);
   cutg->SetPoint(5,22.7124,29.1506);
   cutg->SetPoint(6,24.5642,36.196);
   cutg->SetPoint(7,26.0575,43.6818);
   cutg->SetPoint(8,27.5509,56.4517);
   cutg->SetPoint(9,28.5066,59.9744);
   cutg->SetPoint(10,30.6571,49.4062);
   cutg->SetPoint(11,33.9425,35.7557);
   cutg->SetPoint(12,37.5863,27.8295);
   cutg->SetPoint(13,41.0509,22.1051);
   cutg->SetPoint(14,44.3363,16.821);
   cutg->SetPoint(15,46.7854,15.5);
   cutg->SetPoint(16,48.9956,12.4176);
   cutg->SetPoint(17,50.9071,12.4176);
   cutg->SetPoint(18,46.9646,8.0142);
   cutg->SetPoint(19,43.9181,8.45454);
   cutg->SetPoint(20,40.4535,10.2159);
   cutg->SetPoint(21,37.4071,15.5);
   cutg->SetPoint(22,34.0619,21.2244);
   cutg->SetPoint(23,32.4491,25.6278);
   cutg->SetPoint(24,29.9403,33.1136);
   cutg->SetPoint(25,29.4027,36.6364);
   cutg->SetPoint(26,28.7456,39.7187);
   cutg->SetPoint(27,27.969,33.9943);
   cutg->SetPoint(28,26.6549,25.1875);
   cutg->SetPoint(29,23.25,17.2614);
   cutg->SetPoint(30,20.8009,12.858);
   cutg->SetPoint(31,17.7544,9.33523);
   cutg->SetPoint(32,16.2013,6.69318);
   cutg->SetPoint(33,13.0354,5.37216);
   cutg->SetPoint(34,11.9004,3.61079);
   cutg->SetPoint(35,11.8407,4.49148);

   return cutg;
}
