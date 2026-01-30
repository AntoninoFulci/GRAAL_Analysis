TCutG *myProtonForwCut_2002_d1_test(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CUTG",24);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,22.1023,24.7852);
   cutg->SetPoint(1,24.8694,32.6953);
   cutg->SetPoint(2,26.7851,37.6758);
   cutg->SetPoint(3,27.8494,44.707);
   cutg->SetPoint(4,29.2329,51.4453);
   cutg->SetPoint(5,30.4036,45);
   cutg->SetPoint(6,32.6386,37.3828);
   cutg->SetPoint(7,33.8093,34.7461);
   cutg->SetPoint(8,36.3635,28.5937);
   cutg->SetPoint(9,39.3434,23.6133);
   cutg->SetPoint(10,39.982,25.3711);
   cutg->SetPoint(11,37.5342,30.6445);
   cutg->SetPoint(12,35.0864,36.5039);
   cutg->SetPoint(13,32.9578,42.6562);
   cutg->SetPoint(14,31.5743,47.0508);
   cutg->SetPoint(15,30.1907,53.4961);
   cutg->SetPoint(16,29.9779,59.3555);
   cutg->SetPoint(17,29.5522,63.1641);
   cutg->SetPoint(18,28.0622,51.4453);
   cutg->SetPoint(19,26.6787,43.8281);
   cutg->SetPoint(20,24.6566,36.5039);
   cutg->SetPoint(21,21.6766,30.0586);
   cutg->SetPoint(22,21.6766,28.3008);
   cutg->SetPoint(23,22.1023,24.7852);
   //cutg->Draw("");

   return cutg;
}
