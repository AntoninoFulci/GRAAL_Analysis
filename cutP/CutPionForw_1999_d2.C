TCutG *myPionForwCut_1999_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_1999_d2",10);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.29314,6.67329);
   cutg->SetPoint(1,9.05973,11.6165);
   cutg->SetPoint(2,10.4535,12.4403);
   cutg->SetPoint(3,11.2201,9.55682);
   cutg->SetPoint(4,11.0111,8.73295);
   cutg->SetPoint(5,10.9414,5.84943);
   cutg->SetPoint(6,11.0808,4.61364);
   cutg->SetPoint(7,10.3142,2.96591);
   cutg->SetPoint(8,8.99004,2.14204);
   cutg->SetPoint(9,8.29314,6.67329);
   
   return cutg;
}
