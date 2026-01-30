TCutG *myPionForwCut_2000_uv2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2000_uv2",11);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,9.0531,2.64678);
   cutg->SetPoint(1,8.77876,7.22774);
   cutg->SetPoint(2,9.19027,10.7907);
   cutg->SetPoint(3,9.87611,14.3537);
   cutg->SetPoint(4,11.042,14.8627);
   cutg->SetPoint(5,11.7279,6.71875);
   cutg->SetPoint(6,10.7677,1.62879);
   cutg->SetPoint(7,10.2876,1.62879);
   cutg->SetPoint(8,8.98451,1.62879);
   cutg->SetPoint(9,9.19027,1.11979);
   cutg->SetPoint(10,9.0531,2.64678);
   
   return cutg;
}
