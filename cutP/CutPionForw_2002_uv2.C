TCutG *myPionForwCut_2002_uv2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2002_uv2",8);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,9.71498,15.883);
   cutg->SetPoint(1,10.1558,18.7234);
   cutg->SetPoint(2,11.618,14.3351);
   cutg->SetPoint(3,11.5577,5.0277);
   cutg->SetPoint(4,10.1558,-1.75532);
   cutg->SetPoint(5,8.99838,5.0277);
   cutg->SetPoint(6,9.40787,10.741);
   cutg->SetPoint(7,9.71498,15.883);
   
   return cutg;
}
