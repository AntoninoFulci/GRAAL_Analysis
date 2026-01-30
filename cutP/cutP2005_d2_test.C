TCutG* myProtonForwCut_2005_d2_test()
{
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2005_d2_test",17);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,23.0287,23.763);
   cutg->SetPoint(1,25.6402,31.0872);
   cutg->SetPoint(2,27.5395,39.2253);
   cutg->SetPoint(3,28.3704,42.2092);
   cutg->SetPoint(4,30.151,37.0551);
   cutg->SetPoint(5,32.2878,28.6458);
   cutg->SetPoint(6,34.7806,25.1194);
   cutg->SetPoint(7,35.1367,29.1884);
   cutg->SetPoint(8,32.4065,34.885);
   cutg->SetPoint(9,30.8633,41.1241);
   cutg->SetPoint(10,28.8453,47.092);
   cutg->SetPoint(11,27.5395,42.4805);
   cutg->SetPoint(12,25.4028,35.6988);
   cutg->SetPoint(13,24.4531,30.0022);
   cutg->SetPoint(14,22.9099,25.9332);
   cutg->SetPoint(15,23.1474,24.5768);
   cutg->SetPoint(16,23.0287,23.763);
   //cutg->Draw("");

   return cutg;
}
