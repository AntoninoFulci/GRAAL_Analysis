TCutG *myDeuForwCut_2005_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutDeu2005_d2",15);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,30.6297,51.6667);
   cutg->SetPoint(1,34.6595,75.7778);
   cutg->SetPoint(2,37.8078,57.6944);
   cutg->SetPoint(3,42.0896,40.4722);
   cutg->SetPoint(4,48.6381,24.9722);
   cutg->SetPoint(5,49.8974,21.5278);
   cutg->SetPoint(6,61.3309,9.33442);
   cutg->SetPoint(7,61.1151,5.10687);
   cutg->SetPoint(8,49.7715,13.7778);
   cutg->SetPoint(9,43.6329,23.1444);
   cutg->SetPoint(10,38.9925,37.7999);
   cutg->SetPoint(11,34.7838,53.5827);
   cutg->SetPoint(12,32.6446,40.4722);
   cutg->SetPoint(13,30.7556,50.8056);
   cutg->SetPoint(14,30.6297,51.6667);

   return cutg;
}
