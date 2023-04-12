TCutG *myProtonForwCut_2005_d2(){ 
   // cout<<"Il taglio 2005_d2 è stato caricato"<<endl;
   
   TCutG *cutg = new TCutG("CUTG",35);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.3144,7.45649);
   cutg->SetPoint(1,11.4446,7.23032);
   cutg->SetPoint(2,12.8249,8.96429);
   cutg->SetPoint(3,15.2468,12.583);
   cutg->SetPoint(4,19.049,18.9911);
   cutg->SetPoint(5,22.1741,24.8715);
   cutg->SetPoint(6,25.4034,34.3706);
   cutg->SetPoint(7,26.8878,42.0603);
   cutg->SetPoint(8,28.5025,56.0828);
   cutg->SetPoint(9,31.0286,45.3775);
   cutg->SetPoint(10,33.5287,36.1799);
   cutg->SetPoint(11,37.8257,26.8316);
   cutg->SetPoint(12,42.2529,18.1618);
   cutg->SetPoint(13,46.6281,11.4521);
   cutg->SetPoint(14,54.0763,4.5163);
   cutg->SetPoint(15,47.5917,7.98422);
   cutg->SetPoint(16,46.0291,9.34123);
   cutg->SetPoint(17,41.9665,14.1662);
   cutg->SetPoint(18,39.0237,18.388);
   cutg->SetPoint(19,35.5861,23.1375);
   cutg->SetPoint(20,32.4609,29.0933);
   cutg->SetPoint(21,30.2473,35.2752);
   cutg->SetPoint(22,29.414,37.8385);
   cutg->SetPoint(23,29.0233,37.4615);
   cutg->SetPoint(24,27.7472,33.089);
   cutg->SetPoint(25,26.3409,28.1132);
   cutg->SetPoint(26,24.4138,22.3836);
   cutg->SetPoint(27,23.1898,19.8958);
   cutg->SetPoint(28,22.2262,17.7849);
   cutg->SetPoint(29,20.4032,14.9955);
   cutg->SetPoint(30,18.5282,12.583);
   cutg->SetPoint(31,14.5176,7.53188);
   cutg->SetPoint(32,12.0957,4.96864);
   cutg->SetPoint(33,11.8352,5.57175);
   cutg->SetPoint(34,11.3144,7.45649);
  
   return cutg;
}
