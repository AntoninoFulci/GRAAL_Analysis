TCutG *myPionForwCut_1998_uv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_1998_uv",7);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.3266,83.5937);
   cutg->SetPoint(1,11.8549,114.844);
   cutg->SetPoint(2,11.1153,165.625);
   cutg->SetPoint(3,9.74176,165.625);
   cutg->SetPoint(4,9.00215,138.281);
   cutg->SetPoint(5,9.00215,91.4062);
   cutg->SetPoint(6,11.3266,83.5937);
   
   return cutg;
}
