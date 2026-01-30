TCutG *myPionForwCut_2001_uv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2001_uv",9);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,10.7407,4.29307);
   cutg->SetPoint(1,11.0792,8.45798);
   cutg->SetPoint(2,10.515,10.0599);
   cutg->SetPoint(3,8.59706,10.3803);
   cutg->SetPoint(4,8.59706,6.53571);
   cutg->SetPoint(5,8.93553,4.61344);
   cutg->SetPoint(6,10.4022,4.61344);
   cutg->SetPoint(7,10.9663,4.29307);
   cutg->SetPoint(8,10.7407,4.29307);
   
   return cutg;
}
