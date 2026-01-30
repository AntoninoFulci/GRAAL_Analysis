TCutG *myProtonForwCut_1999_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_1999_vis",34);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,12.5044,100.483);
   cutg->SetPoint(1,16.5664,169.517);
   cutg->SetPoint(2,19.5,227.045);
   cutg->SetPoint(3,21.6814,296.08);
   cutg->SetPoint(4,25.6681,449.489);
   cutg->SetPoint(5,27.6239,568.381);
   cutg->SetPoint(6,29.2788,691.108);
   cutg->SetPoint(7,30.1062,748.636);
   cutg->SetPoint(8,31.4602,641.25);
   cutg->SetPoint(9,35.0708,495.511);
   cutg->SetPoint(10,37.5531,376.619);
   cutg->SetPoint(11,41.0885,265.398);
   cutg->SetPoint(12,45.3009,184.858);
   cutg->SetPoint(13,48.385,127.33);
   cutg->SetPoint(14,52.5221,161.847);
   cutg->SetPoint(15,47.5575,246.222);
   cutg->SetPoint(16,44.3982,345.937);
   cutg->SetPoint(17,40.6372,430.312);
   cutg->SetPoint(18,37.177,583.722);
   cutg->SetPoint(19,35.2965,664.261);
   cutg->SetPoint(20,33.115,771.648);
   cutg->SetPoint(21,31.7611,894.375);
   cutg->SetPoint(22,30.1814,994.091);
   cutg->SetPoint(23,28.8274,997.926);
   cutg->SetPoint(24,27.323,863.693);
   cutg->SetPoint(25,26.1195,714.119);
   cutg->SetPoint(26,24.3894,599.062);
   cutg->SetPoint(27,22.0575,476.335);
   cutg->SetPoint(28,19.1239,365.114);
   cutg->SetPoint(29,16.792,292.244);
   cutg->SetPoint(30,14.0088,207.869);
   cutg->SetPoint(31,13.031,188.693);
   cutg->SetPoint(32,11.9027,169.517);
   cutg->SetPoint(33,12.5044,100.483);

   return cutg;
}
