TCutG *myPionForwCut_1999_d1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_1999_d1",7);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.97436,3.78383);
   cutg->SetPoint(1,9.35897,11.6774);
   cutg->SetPoint(2,11.2821,13.6508);
   cutg->SetPoint(3,12.0513,5.09942);
   cutg->SetPoint(4,10.8974,3.78383);
   cutg->SetPoint(5,9.23077,3.78383);
   cutg->SetPoint(6,8.97436,3.78383);
   
   return cutg;
}
