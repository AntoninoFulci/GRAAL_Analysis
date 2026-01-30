TCutG *myPionForwCut_2005_d1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion_2005_d1",9);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,9.74427,2.51953);
   cutg->SetPoint(1,10.1812,11.3845);
   cutg->SetPoint(2,10.8367,15.5838);
   cutg->SetPoint(3,12.0383,15.5838);
   cutg->SetPoint(4,12.5845,9.98481);
   cutg->SetPoint(5,13.0215,7.65191);
   cutg->SetPoint(6,12.9122,3.45269);
   cutg->SetPoint(7,11.9291,2.98611);
   cutg->SetPoint(8,9.74427,2.51953);
   
   return cutg;
}
