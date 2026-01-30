TCutG *myPionForwCut_2002_d1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2002_d1",7);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,9.08407,4.98485);
   cutg->SetPoint(1,9.14823,11.2159);
   cutg->SetPoint(2,10.0465,12.9962);
   cutg->SetPoint(3,10.7522,10.7708);
   cutg->SetPoint(4,10.9447,8.54545);
   cutg->SetPoint(5,11.1372,5.875);
   cutg->SetPoint(6,9.08407,4.98485);
   
   return cutg;
}
