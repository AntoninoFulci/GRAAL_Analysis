TCutG *myDeuForwCut_2006_d(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CutDeu2006_d",24);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,32.5155,53.9432);
   cutg->SetPoint(1,35.1106,63.2898);
   cutg->SetPoint(2,36.1792,68.6307);
   cutg->SetPoint(3,38.698,60.6193);
   cutg->SetPoint(4,41.7511,50.3826);
   cutg->SetPoint(5,45.4912,41.4811);
   cutg->SetPoint(6,49.6892,31.2443);
   cutg->SetPoint(7,53.5055,23.678);
   cutg->SetPoint(8,57.3982,19.6723);
   cutg->SetPoint(9,61.6726,14.3314);
   cutg->SetPoint(10,63.1228,11.661);
   cutg->SetPoint(11,63.8097,8.99053);
   cutg->SetPoint(12,60.6803,9.88068);
   cutg->SetPoint(13,57.0929,10.7708);
   cutg->SetPoint(14,52.3606,12.1061);
   cutg->SetPoint(15,48.7732,19.2273);
   cutg->SetPoint(16,45.7965,25.4583);
   cutg->SetPoint(17,42.2091,32.1345);
   cutg->SetPoint(18,39.8429,40.1458);
   cutg->SetPoint(19,37.7058,46.822);
   cutg->SetPoint(20,36.2555,44.1515);
   cutg->SetPoint(21,35.0343,40.1458);
   cutg->SetPoint(22,33.2788,51.2727);
   cutg->SetPoint(23,32.5155,53.9432);
   
   return cutg;
}
