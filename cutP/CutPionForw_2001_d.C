TCutG *myPionForwCut_2001_d(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2001_d",10);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.2279,5.71529);
   cutg->SetPoint(1,11.0996,9.14806);
   cutg->SetPoint(2,10.0088,11.4366);
   cutg->SetPoint(3,9.23894,8.76664);
   cutg->SetPoint(4,8.34071,8.0038);
   cutg->SetPoint(5,8.59734,3.04536);
   cutg->SetPoint(6,10.073,4.95245);
   cutg->SetPoint(7,11.4845,5.71529);
   cutg->SetPoint(8,11.1637,8.0038);
   cutg->SetPoint(9,11.2279,5.71529);
   return cutg;
}
