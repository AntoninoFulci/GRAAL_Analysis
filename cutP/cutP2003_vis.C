TCutG *myProtonForwCut_2003_vis(){ 
   // cout<<"Il taglio 2003_vis è stato caricato"<<endl;

   
   TCutG *cutg = new TCutG("CUTG",42);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.6777,6.55222);
   cutg->SetPoint(1,11.6777,10.657);
   cutg->SetPoint(2,14.5547,15.1894);
   cutg->SetPoint(3,16.5964,18.61);
   cutg->SetPoint(4,18.7309,23.0569);
   cutg->SetPoint(5,20.4632,26.5631);
   cutg->SetPoint(6,22.1956,30.4968);
   cutg->SetPoint(7,25.0416,37.5092);
   cutg->SetPoint(8,26.5883,44.6926);
   cutg->SetPoint(9,28.0113,53.4153);
   cutg->SetPoint(10,28.7538,60.2566);
   cutg->SetPoint(11,29.4034,60.4276);
   cutg->SetPoint(12,29.9912,57.6911);
   cutg->SetPoint(13,31.5998,47.5146);
   cutg->SetPoint(14,34.0436,37.9368);
   cutg->SetPoint(15,36.4256,31.0099);
   cutg->SetPoint(16,39.8903,24.3397);
   cutg->SetPoint(17,43.6025,17.4983);
   cutg->SetPoint(18,48.8614,11.9398);
   cutg->SetPoint(19,50.6557,9.0322);
   cutg->SetPoint(20,48.0881,10.486);
   cutg->SetPoint(21,44.8399,13.3935);
   cutg->SetPoint(22,41.0658,18.9521);
   cutg->SetPoint(23,37.8796,23.9976);
   cutg->SetPoint(24,35.1264,29.5562);
   cutg->SetPoint(25,33.4249,34.6872);
   cutg->SetPoint(26,31.8163,40.7588);
   cutg->SetPoint(27,30.1768,48.1133);
   cutg->SetPoint(28,29.7127,50.0801);
   cutg->SetPoint(29,29.2797,50.1657);
   cutg->SetPoint(30,28.8775,47.0015);
   cutg->SetPoint(31,28.3516,42.6402);
   cutg->SetPoint(32,27.5164,38.792);
   cutg->SetPoint(33,26.5265,34.003);
   cutg->SetPoint(34,24.6085,29.0431);
   cutg->SetPoint(35,22.7215,24.0831);
   cutg->SetPoint(36,20.6798,19.6362);
   cutg->SetPoint(37,17.8956,14.9328);
   cutg->SetPoint(38,15.4518,10.9991);
   cutg->SetPoint(39,13.5957,9.0322);
   cutg->SetPoint(40,12.6676,7.74945);
   cutg->SetPoint(41,11.6777,6.55222);

   return cutg;
}
