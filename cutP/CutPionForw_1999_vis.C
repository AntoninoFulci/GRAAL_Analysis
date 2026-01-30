TCutG *myPionForwCut_1999_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_1999_vis",10);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("Dedx_tof");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.64183,9.16015);
   cutg->SetPoint(1,9.57665,14.6289);
   cutg->SetPoint(2,10.6153,17.3633);
   cutg->SetPoint(3,10.8231,15.9961);
   cutg->SetPoint(4,11.3424,11.8945);
   cutg->SetPoint(5,11.4463,9.16015);
   cutg->SetPoint(6,10.9269,2.32422);
   cutg->SetPoint(7,9.05731,3.00781);
   cutg->SetPoint(8,9.05731,8.47656);
   cutg->SetPoint(9,8.64183,9.16015);
  
   return cutg;
}
