TCutG *myProtonForwCut_2002_vis1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2002_vis1",40);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,12.3894,5.44602);
   cutg->SetPoint(1,11.5398,10.4318);
   cutg->SetPoint(2,13.9469,15.4176);
   cutg->SetPoint(3,16.4956,18.1023);
   cutg->SetPoint(4,19.469,26.5398);
   cutg->SetPoint(5,22.5133,32.6761);
   cutg->SetPoint(6,25.1327,44.9489);
   cutg->SetPoint(7,26.6903,54.9205);
   cutg->SetPoint(8,27.823,66.4261);
   cutg->SetPoint(9,28.6726,71.4119);
   cutg->SetPoint(10,30.5841,61.0568);
   cutg->SetPoint(11,32.9204,51.8523);
   cutg->SetPoint(12,34.6903,45.7159);
   cutg->SetPoint(13,35.8938,40.7301);
   cutg->SetPoint(14,38.2301,34.9773);
   cutg->SetPoint(15,41.2035,28.0739);
   cutg->SetPoint(16,44.3186,23.4716);
   cutg->SetPoint(17,49.1327,16.5682);
   cutg->SetPoint(18,52.177,13.8835);
   cutg->SetPoint(19,56.6372,9.28125);
   cutg->SetPoint(20,53.0973,3.91193);
   cutg->SetPoint(21,49.4159,6.21307);
   cutg->SetPoint(22,46.4425,7.36364);
   cutg->SetPoint(23,42.9027,12.3494);
   cutg->SetPoint(24,39.3628,16.1847);
   cutg->SetPoint(25,36.6018,25.0057);
   cutg->SetPoint(26,34.1239,30.7585);
   cutg->SetPoint(27,32,37.2784);
   cutg->SetPoint(28,30.5841,44.1818);
   cutg->SetPoint(29,29.2389,49.5511);
   cutg->SetPoint(30,28.177,42.6477);
   cutg->SetPoint(31,27.1858,36.5114);
   cutg->SetPoint(32,24.7788,28.0739);
   cutg->SetPoint(33,22.7257,23.0881);
   cutg->SetPoint(34,20.0354,15.8011);
   cutg->SetPoint(35,18.2655,15.0341);
   cutg->SetPoint(36,16.0708,11.1989);
   cutg->SetPoint(37,14.3717,7.74716);
   cutg->SetPoint(38,12.3894,5.82954);
   cutg->SetPoint(39,12.3894,5.44602);

   return cutg;
}
