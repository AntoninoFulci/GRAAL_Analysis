TCutG *myProtonForwCut_2002_uv2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2002_uv2",40);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,12.9889,15);
   cutg->SetPoint(1,15.5741,18.9062);
   cutg->SetPoint(2,18.0332,22.8125);
   cutg->SetPoint(3,20.177,28.2812);
   cutg->SetPoint(4,22.3208,35.3125);
   cutg->SetPoint(5,23.708,41.5625);
   cutg->SetPoint(6,26.167,50.9375);
   cutg->SetPoint(7,27.5542,67.3437);
   cutg->SetPoint(8,29.0044,72.8125);
   cutg->SetPoint(9,30.4546,65);
   cutg->SetPoint(10,31.9679,57.9687);
   cutg->SetPoint(11,34.3009,51.7187);
   cutg->SetPoint(12,35.2467,43.9062);
   cutg->SetPoint(13,37.3274,38.4375);
   cutg->SetPoint(14,40.2909,29.0625);
   cutg->SetPoint(15,42.5608,25.9375);
   cutg->SetPoint(16,45.5874,21.25);
   cutg->SetPoint(17,47.8573,18.125);
   cutg->SetPoint(18,50.8208,13.4375);
   cutg->SetPoint(19,53.8473,11.875);
   cutg->SetPoint(20,49.4336,4.84375);
   cutg->SetPoint(21,47.2898,4.84375);
   cutg->SetPoint(22,44.9569,4.84375);
   cutg->SetPoint(23,42.75,9.53125);
   cutg->SetPoint(24,39.8496,14.2187);
   cutg->SetPoint(25,38.3363,18.9062);
   cutg->SetPoint(26,35.7511,24.375);
   cutg->SetPoint(27,32.8507,32.1875);
   cutg->SetPoint(28,31.0852,40);
   cutg->SetPoint(29,29.7611,44.6875);
   cutg->SetPoint(30,29.2566,48.5937);
   cutg->SetPoint(31,28.1847,38.4375);
   cutg->SetPoint(32,26.6715,32.1875);
   cutg->SetPoint(33,22.6361,17.3437);
   cutg->SetPoint(34,20.1139,11.875);
   cutg->SetPoint(35,18.3485,9.53125);
   cutg->SetPoint(36,14.5022,8.75);
   cutg->SetPoint(37,12.2323,8.75);
   cutg->SetPoint(38,12.1692,13.4375);
   cutg->SetPoint(39,12.9889,15);

   return cutg;
}
