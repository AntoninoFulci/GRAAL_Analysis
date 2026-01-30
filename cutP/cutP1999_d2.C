TCutG *myProtonForwCut_1999_d2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_1999_d2",29);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,12.3352,12.8523);
   cutg->SetPoint(1,16.1681,18.2074);
   cutg->SetPoint(2,19.4436,23.5625);
   cutg->SetPoint(3,23.2765,35.5085);
   cutg->SetPoint(4,26.6217,50.3381);
   cutg->SetPoint(5,28.7821,66.4034);
   cutg->SetPoint(6,30.2456,63.9318);
   cutg->SetPoint(7,32.5454,50.3381);
   cutg->SetPoint(8,36.1692,40.4517);
   cutg->SetPoint(9,41.1869,27.2699);
   cutg->SetPoint(10,47.5288,18.6193);
   cutg->SetPoint(11,51.7102,12.4403);
   cutg->SetPoint(12,56.5188,5.02557);
   cutg->SetPoint(13,48.7135,5.4375);
   cutg->SetPoint(14,43.6958,9.55682);
   cutg->SetPoint(15,38.8872,17.3835);
   cutg->SetPoint(16,34.8451,27.6818);
   cutg->SetPoint(17,32.3363,36.7443);
   cutg->SetPoint(18,29.8274,45.8068);
   cutg->SetPoint(19,29.2699,48.6903);
   cutg->SetPoint(20,27.8761,39.6278);
   cutg->SetPoint(21,24.9491,26.446);
   cutg->SetPoint(22,20.0708,14.5);
   cutg->SetPoint(23,15.0531,8.32102);
   cutg->SetPoint(24,11.9867,5.84943);
   cutg->SetPoint(25,11.708,10.7926);
   cutg->SetPoint(26,13.2412,14.9119);
   cutg->SetPoint(27,17.6316,20.679);
   cutg->SetPoint(28,12.3352,12.8523);

   return cutg;
}
