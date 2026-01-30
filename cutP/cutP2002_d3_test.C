TCutG *myProtonForwCut_2002_d3_test(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2002_d3_test",25);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,18.3725,18.751);
   cutg->SetPoint(1,20.4355,18.5062);
   cutg->SetPoint(2,24.5616,30.9906);
   cutg->SetPoint(3,27.5415,40.5375);
   cutg->SetPoint(4,28,51.5531);
   cutg->SetPoint(5,28.9169,55.7146);
   cutg->SetPoint(6,30.7507,42.251);
   cutg->SetPoint(7,34.1891,34.4177);
   cutg->SetPoint(8,40.6074,18.5062);
   cutg->SetPoint(9,41.7536,20.7094);
   cutg->SetPoint(10,34.6476,37.6);
   cutg->SetPoint(11,32.4699,42.7406);
   cutg->SetPoint(12,31.2092,48.8604);
   cutg->SetPoint(13,30.5215,52.7771);
   cutg->SetPoint(14,29.3754,58.4073);
   cutg->SetPoint(15,28.2292,60.3656);
   cutg->SetPoint(16,27.4269,53.7562);
   cutg->SetPoint(17,26.9685,47.1469);
   cutg->SetPoint(18,25.4785,38.3344);
   cutg->SetPoint(19,23.5301,32.4594);
   cutg->SetPoint(20,22.0401,26.8292);
   cutg->SetPoint(21,20.3209,23.8917);
   cutg->SetPoint(22,19.5186,22.1781);
   cutg->SetPoint(23,19.1748,21.199);
   cutg->SetPoint(24,18.3725,18.751);
   //cutg->Draw("");

   return cutg;
}
