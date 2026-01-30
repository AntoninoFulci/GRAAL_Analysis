TCutG *myPionForwCut_2000_uv1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2000_uv1",8);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.59142,3.06667);
   cutg->SetPoint(1,8.73134,11.5);
   cutg->SetPoint(2,10.2705,11.5);
   cutg->SetPoint(3,11.6698,9.2);
   cutg->SetPoint(4,11.3899,3.83333);
   cutg->SetPoint(5,9.5709,4.6);
   cutg->SetPoint(6,8.87127,3.06667);
   cutg->SetPoint(7,8.59142,3.06667);
   
   return cutg;
}
