TCutG* myDeuForwCut_1999_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwDeu_1999_d2",20);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,33.0984,51.1425);
   cutg->SetPoint(1,34.2104,60.1989);
   cutg->SetPoint(2,34.9053,64.727);
   cutg->SetPoint(3,38.5191,48.555);
   cutg->SetPoint(4,42.6889,33.0298);
   cutg->SetPoint(5,46.3027,27.2078);
   cutg->SetPoint(6,49.7776,20.739);
   cutg->SetPoint(7,52.9744,14.917);
   cutg->SetPoint(8,56.1712,12.3295);
   cutg->SetPoint(9,56.1712,19.4452);
   cutg->SetPoint(10,51.8624,25.914);
   cutg->SetPoint(11,46.8587,36.9111);
   cutg->SetPoint(12,40.882,53.73);
   cutg->SetPoint(13,37.8242,67.9615);
   cutg->SetPoint(14,35.6003,82.8398);
   cutg->SetPoint(15,35.4613,88.0148);
   cutg->SetPoint(16,33.6544,74.4303);
   cutg->SetPoint(17,32.1255,60.8457);
   cutg->SetPoint(18,31.9865,58.2582);
   cutg->SetPoint(19,33.0984,51.1425);
   
   return cutg;
}
