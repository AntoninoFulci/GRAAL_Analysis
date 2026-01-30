TCutG *myProtonForwCut_2006_d_test(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2006_d_test",21);
   cutg->SetVarX("Tof(ns)");
   cutg->SetVarY("DE(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,24.6754,21.4297);
   cutg->SetPoint(1,27.7372,28.0312);
   cutg->SetPoint(2,28.4331,32.0937);
   cutg->SetPoint(3,29.4073,37.849);
   cutg->SetPoint(4,30.5207,43.2656);
   cutg->SetPoint(5,32.4691,39.3724);
   cutg->SetPoint(6,34.835,30.9089);
   cutg->SetPoint(7,36.5051,25.8307);
   cutg->SetPoint(8,39.5669,22.276);
   cutg->SetPoint(9,37.201,30.0625);
   cutg->SetPoint(10,34.5567,37.0026);
   cutg->SetPoint(11,32.3299,43.9427);
   cutg->SetPoint(12,31.6341,49.3594);
   cutg->SetPoint(13,30.9382,52.5755);
   cutg->SetPoint(14,29.8248,47.4974);
   cutg->SetPoint(15,28.5722,39.7109);
   cutg->SetPoint(16,27.4589,31.9245);
   cutg->SetPoint(17,25.7888,27.5234);
   cutg->SetPoint(18,23.8404,22.9531);
   cutg->SetPoint(19,25.3713,21.599);
   cutg->SetPoint(20,24.6754,21.4297);
   //cutg->Draw("");

   return cutg;
}
