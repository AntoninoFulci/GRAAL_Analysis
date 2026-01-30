bool CutEtaPro(int nphotons, double Eg){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutEtaPro",12);
   cutg->SetVarX("beam energy(GeV)");
   cutg->SetVarY("proton theta(°)");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.697496,1.05126);
   cutg->SetPoint(1,0.715861,9.35065);
   cutg->SetPoint(2,0.75055,20.186);
   cutg->SetPoint(3,0.842376,30.5602);
   cutg->SetPoint(4,1.01174,41.9719);
   cutg->SetPoint(5,1.26477,50.6171);
   cutg->SetPoint(6,1.47087,54.7668);
   cutg->SetPoint(7,1.60963,56.6111);
   cutg->SetPoint(8,1.61167,41.5108);
   cutg->SetPoint(9,1.60555,23.644);
   cutg->SetPoint(10,1.61371,0.244371);
   cutg->SetPoint(11,0.697496,1.05126);
   //cutg->Draw("");

   if(nphotons>=2 && Eg>=0.708){
     if(cutg->IsInside()){

     }
   }

}
