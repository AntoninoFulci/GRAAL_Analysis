TCutG *myPionForwCut_2002_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2002_d2",9);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.82633,5.00947);
   cutg->SetPoint(1,8.65155,9.36553);
   cutg->SetPoint(2,10.1372,12.0881);
   cutg->SetPoint(3,11.7976,9.36553);
   cutg->SetPoint(4,11.7102,3.92045);
   cutg->SetPoint(5,9.96239,2.83144);
   cutg->SetPoint(6,9.00111,5.00947);
   cutg->SetPoint(7,8.91372,6.64299);
   cutg->SetPoint(8,8.82633,5.00947);
   
   return cutg;
}
