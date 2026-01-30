TCutG *myPionForwCut_1999_uv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
TCutG *cutg = new TCutG("CUTForwPion_1999_uv",9);
cutg->SetVarX("Tof_trf");
cutg->SetVarY("De_trf");
cutg->SetTitle("Graph");
cutg->SetFillStyle(1000);
cutg->SetPoint(0,8.33811,98.2812);
cutg->SetPoint(1,9.19771,124.844);
cutg->SetPoint(2,10.6304,122.63);
cutg->SetPoint(3,11.6332,98.2812);
cutg->SetPoint(4,11.7765,82.7865);
cutg->SetPoint(5,10.7736,69.5052);
cutg->SetPoint(6,8.76791,78.3594);
cutg->SetPoint(7,8.33811,91.6406);
cutg->SetPoint(8,8.33811,98.2812);
   
   return cutg;
}
