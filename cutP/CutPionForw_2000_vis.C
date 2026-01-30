TCutG* myPionForwCut_2000_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2000_vis",9);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.36283,5.8125);
   cutg->SetPoint(1,8.76106,10.2159);
   cutg->SetPoint(2,9.75664,12.858);
   cutg->SetPoint(3,10.6858,11.5369);
   cutg->SetPoint(4,11.6814,7.13352);
   cutg->SetPoint(5,11.0177,5.37216);
   cutg->SetPoint(6,9.15929,4.93182);
   cutg->SetPoint(7,8.36283,5.8125);
   cutg->SetPoint(8,8.36283,5.8125);
   
   return cutg;
}
