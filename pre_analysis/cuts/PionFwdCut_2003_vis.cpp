TCutG* PionFwdCut_2003_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("PionFwdCut_2003_vis",8);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,10.6991,5.32292);
   cutg->SetPoint(1,11.625,7.09929);
   cutg->SetPoint(2,11.0466,9.82979);
   cutg->SetPoint(3,9.16698,9.48847);
   cutg->SetPoint(4,8.73321,7.09929);
   cutg->SetPoint(5,9.0531,4.77604);
   cutg->SetPoint(6,10.0819,4.22917);
   cutg->SetPoint(7,10.6991,5.32292);
   
   return cutg;
}
