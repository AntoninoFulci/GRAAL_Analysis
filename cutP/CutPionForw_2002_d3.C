TCutG *myPionForwCut_2002_d3(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2002_d3",10);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.84956,9.60439);
   cutg->SetPoint(1,9.84071,11.1841);
   cutg->SetPoint(2,10.4779,10.8681);
   cutg->SetPoint(3,10.9027,8.97253);
   cutg->SetPoint(4,11.0442,6.12912);
   cutg->SetPoint(5,10.7611,4.54945);
   cutg->SetPoint(6,10.1239,3.91758);
   cutg->SetPoint(7,9.27434,4.23352);
   cutg->SetPoint(8,8.92035,4.54945);
   cutg->SetPoint(9,8.84956,9.60439);
   
   return cutg;
}
