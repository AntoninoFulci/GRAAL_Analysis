TCutG *myPionForwCut_2002_vis2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2002_vis2",9);
   cutg->SetVarX("tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.51217,4.08791);
   cutg->SetPoint(1,9.9458,2.95238);
   cutg->SetPoint(2,11.5586,4.08791);
   cutg->SetPoint(3,11.7378,8.63004);
   cutg->SetPoint(4,10.7522,10.3333);
   cutg->SetPoint(5,9.85619,10.3333);
   cutg->SetPoint(6,8.78097,8.06227);
   cutg->SetPoint(7,8.51217,7.21062);
   cutg->SetPoint(8,8.51217,4.08791);
   
   return cutg;
}
