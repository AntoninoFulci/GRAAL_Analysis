TCutG *myPionForwCut_2000_fuv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2000_fuv",10);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,12.4128,5.90798);
   cutg->SetPoint(1,12.8202,9.15017);
   cutg->SetPoint(2,11.435,17.0755);
   cutg->SetPoint(3,9.64237,15.9948);
   cutg->SetPoint(4,8.74606,9.51042);
   cutg->SetPoint(5,8.58309,5.1875);
   cutg->SetPoint(6,9.47941,4.46701);
   cutg->SetPoint(7,10.7016,4.10677);
   cutg->SetPoint(8,12.2498,4.46701);
   cutg->SetPoint(9,12.4128,5.90798);
   
   return cutg;
}
