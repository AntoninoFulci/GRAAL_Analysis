TCutG *myPionForwCut_2006_d(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2006_d",7);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,9.88013,-0.166668);
   cutg->SetPoint(1,10.6847,12.3333);
   cutg->SetPoint(2,11.972,14);
   cutg->SetPoint(3,13.7421,9);
   cutg->SetPoint(4,13.4202,4);
   cutg->SetPoint(5,12.9375,3.16667);
   cutg->SetPoint(6,9.88013,-0.166668);
   
   return cutg;
}
