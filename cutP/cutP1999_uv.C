TCutG *myProtonForwCut_1999_uv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_1999_uv",43);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,13.8053,111.562);
   cutg->SetPoint(1,12.3009,157.443);
   cutg->SetPoint(2,13.7168,212.983);
   cutg->SetPoint(3,17.7876,324.062);
   cutg->SetPoint(4,21.1504,401.335);
   cutg->SetPoint(5,22.7434,493.097);
   cutg->SetPoint(6,24.6018,563.125);
   cutg->SetPoint(7,26.6372,674.205);
   cutg->SetPoint(8,27.6106,785.284);
   cutg->SetPoint(9,27.8761,826.335);
   cutg->SetPoint(10,27.9646,903.608);
   cutg->SetPoint(11,28.1416,947.074);
   cutg->SetPoint(12,29.3805,949.489);
   cutg->SetPoint(13,31.2389,901.193);
   cutg->SetPoint(14,32.6549,799.773);
   cutg->SetPoint(15,33.3628,717.67);
   cutg->SetPoint(16,35.5752,609.006);
   cutg->SetPoint(17,36.2832,546.222);
   cutg->SetPoint(18,38.5841,476.193);
   cutg->SetPoint(19,40.7965,408.58);
   cutg->SetPoint(20,44.9558,309.574);
   cutg->SetPoint(21,47.4336,244.375);
   cutg->SetPoint(22,50.177,200.909);
   cutg->SetPoint(23,50.4425,147.784);
   cutg->SetPoint(24,47.9646,138.125);
   cutg->SetPoint(25,43.9823,212.983);
   cutg->SetPoint(26,41.7699,283.011);
   cutg->SetPoint(27,38.8496,372.358);
   cutg->SetPoint(28,35.3982,459.29);
   cutg->SetPoint(29,33.2743,575.199);
   cutg->SetPoint(30,32.1239,664.545);
   cutg->SetPoint(31,30.531,732.159);
   cutg->SetPoint(32,30.0885,647.642);
   cutg->SetPoint(33,28.5841,529.318);
   cutg->SetPoint(34,26.8142,452.045);
   cutg->SetPoint(35,25.0442,382.017);
   cutg->SetPoint(36,22.4779,311.989);
   cutg->SetPoint(37,20.4425,251.619);
   cutg->SetPoint(38,17.7876,191.25);
   cutg->SetPoint(39,16.2832,167.102);
   cutg->SetPoint(40,14.7788,128.466);
   cutg->SetPoint(41,13.6283,104.318);
   cutg->SetPoint(42,13.8053,111.562);

   return cutg;
}
