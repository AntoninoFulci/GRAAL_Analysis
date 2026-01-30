TCutG *myProtonForwCut_2002_uv1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2002_uv1",41);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,29.089,67.0502);
   cutg->SetPoint(1,31.396,60.6108);
   cutg->SetPoint(2,32.5227,52.5616);
   cutg->SetPoint(3,34.5077,43.5062);
   cutg->SetPoint(4,36.7611,34.2495);
   cutg->SetPoint(5,39.9264,27.8101);
   cutg->SetPoint(6,42.9845,22.5781);
   cutg->SetPoint(7,45.667,18.151);
   cutg->SetPoint(8,45.9889,16.1387);
   cutg->SetPoint(9,41.7506,15.3338);
   cutg->SetPoint(10,39.4972,15.9375);
   cutg->SetPoint(11,37.2439,19.7609);
   cutg->SetPoint(12,34.776,26.4015);
   cutg->SetPoint(13,32.9519,32.2372);
   cutg->SetPoint(14,31.5033,38.0729);
   cutg->SetPoint(15,30.2157,45.5185);
   cutg->SetPoint(16,29.25,51.5554);
   cutg->SetPoint(17,27.9087,43.1037);
   cutg->SetPoint(18,26.6211,36.4631);
   cutg->SetPoint(19,25.4408,32.4384);
   cutg->SetPoint(20,23.9386,28.6151);
   cutg->SetPoint(21,21.7389,23.1818);
   cutg->SetPoint(22,20.1831,19.9621);
   cutg->SetPoint(23,18.4126,17.3461);
   cutg->SetPoint(24,16.6421,14.1264);
   cutg->SetPoint(25,15.0863,12.3153);
   cutg->SetPoint(26,13.906,10.5043);
   cutg->SetPoint(27,13.1012,10.1018);
   cutg->SetPoint(28,12.0282,7.48579);
   cutg->SetPoint(29,11.5454,10.5043);
   cutg->SetPoint(30,13.2085,15.3338);
   cutg->SetPoint(31,15.891,18.5535);
   cutg->SetPoint(32,17.3933,22.5781);
   cutg->SetPoint(33,20.505,29.2187);
   cutg->SetPoint(34,22.2218,36.4631);
   cutg->SetPoint(35,24.2069,43.9086);
   cutg->SetPoint(36,26.2992,52.7628);
   cutg->SetPoint(37,27.8014,62.4219);
   cutg->SetPoint(38,28.3916,64.8366);
   cutg->SetPoint(39,29.089,66.4465);
   cutg->SetPoint(40,29.089,67.0502);

   return cutg;
}
