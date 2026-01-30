TCutG *myProtonForwCut_2000_uv2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2000_uv2",29);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,29.6969,65.7623);
   cutg->SetPoint(1,31.6173,56.0914);
   cutg->SetPoint(2,33.7434,44.8935);
   cutg->SetPoint(3,36.8296,35.7315);
   cutg->SetPoint(4,39.7102,29.1146);
   cutg->SetPoint(5,43.0022,23.0066);
   cutg->SetPoint(6,45.5398,20.9706);
   cutg->SetPoint(7,48.969,13.8447);
   cutg->SetPoint(8,45.2655,12.3177);
   cutg->SetPoint(9,41.6991,12.3177);
   cutg->SetPoint(10,38.8186,19.4437);
   cutg->SetPoint(11,35.3894,26.0606);
   cutg->SetPoint(12,33.6748,33.6955);
   cutg->SetPoint(13,31.9602,37.2585);
   cutg->SetPoint(14,29.9712,44.8935);
   cutg->SetPoint(15,29.2168,48.9654);
   cutg->SetPoint(16,27.365,41.3305);
   cutg->SetPoint(17,25.2389,31.6596);
   cutg->SetPoint(18,23.7301,24.5336);
   cutg->SetPoint(19,20.2323,16.3897);
   cutg->SetPoint(20,16.2544,10.2817);
   cutg->SetPoint(21,13.7168,7.73674);
   cutg->SetPoint(22,12.9624,12.3177);
   cutg->SetPoint(23,18.1748,21.4796);
   cutg->SetPoint(24,22.0155,33.1866);
   cutg->SetPoint(25,25.5133,45.4025);
   cutg->SetPoint(26,27.2279,56.0914);
   cutg->SetPoint(27,28.5996,62.1993);
   cutg->SetPoint(28,29.6969,65.7623);

   return cutg;
}
