TCutG *myProtonForwCut_2000_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2000_vis",32);
   cutg->SetVarX("ddxtof_fow_2000_vis");
   cutg->SetVarY("");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,13.0088,7.13352);
   cutg->SetPoint(1,12.677,11.5369);
   cutg->SetPoint(2,15.1327,16.3807);
   cutg->SetPoint(3,18.5841,21.6648);
   cutg->SetPoint(4,21.7699,29.1506);
   cutg->SetPoint(5,24.0929,38.3977);
   cutg->SetPoint(6,26.0177,46.3239);
   cutg->SetPoint(7,26.9469,57.7727);
   cutg->SetPoint(8,27.8761,63.9375);
   cutg->SetPoint(9,28.7389,69.2216);
   cutg->SetPoint(10,30.7301,58.6534);
   cutg->SetPoint(11,33.1195,48.0852);
   cutg->SetPoint(12,36.4381,38.3977);
   cutg->SetPoint(13,39.292,30.0312);
   cutg->SetPoint(14,43.2743,22.9858);
   cutg->SetPoint(15,47.5885,19.0227);
   cutg->SetPoint(16,49.7788,11.0966);
   cutg->SetPoint(17,45.9956,10.2159);
   cutg->SetPoint(18,42.2124,12.4176);
   cutg->SetPoint(19,39.2257,17.7017);
   cutg->SetPoint(20,36.3053,25.1875);
   cutg->SetPoint(21,32.6549,34.4347);
   cutg->SetPoint(22,30.1991,45.0028);
   cutg->SetPoint(23,29.3363,48.9659);
   cutg->SetPoint(24,27.2788,37.9574);
   cutg->SetPoint(25,25.8186,27.8295);
   cutg->SetPoint(26,22.8982,20.3437);
   cutg->SetPoint(27,20.6416,15.5);
   cutg->SetPoint(28,17.1903,11.0966);
   cutg->SetPoint(29,15.7301,9.33523);
   cutg->SetPoint(30,13.0752,5.8125);
   cutg->SetPoint(31,13.0088,7.13352);
   return cutg;
}
