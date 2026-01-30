TCutG *myPionForwCut_2002_uv1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2002_uv1",15);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.8673,6.07718);
   cutg->SetPoint(1,11.8673,10.1018);
   cutg->SetPoint(2,11.1162,11.9129);
   cutg->SetPoint(3,10.2041,12.3153);
   cutg->SetPoint(4,9.23838,11.108);
   cutg->SetPoint(5,8.80918,8.69318);
   cutg->SetPoint(6,8.86283,4.66856);
   cutg->SetPoint(7,8.86283,2.65625);
   cutg->SetPoint(8,9.66759,1.65009);
   cutg->SetPoint(9,11.0088,1.65009);
   cutg->SetPoint(10,11.76,1.44886);
   cutg->SetPoint(11,11.9746,4.66856);
   cutg->SetPoint(12,11.8673,7.08333);
   cutg->SetPoint(13,11.8673,9.09564);
   cutg->SetPoint(14,11.8673,6.07718);
   
   return cutg;
}
