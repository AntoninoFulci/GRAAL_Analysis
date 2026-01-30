TCutG *myPionForwCut_2005_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2005_d2",9);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.12249,3.51302);
   cutg->SetPoint(1,8.47917,9.78463);
   cutg->SetPoint(2,9.68052,11.5252);
   cutg->SetPoint(3,10.9269,8.44358);
   cutg->SetPoint(4,10.4076,3.82118);
   cutg->SetPoint(5,9.16117,3.51302);
   cutg->SetPoint(6,8.89583,3.6385);
   cutg->SetPoint(7,8.7457,3.20486);
   cutg->SetPoint(8,8.12249,3.51302);
   
   return cutg;
}
