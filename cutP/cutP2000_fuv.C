TCutG *myProtonForwCut_2000_fuv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2000_fuv",40);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,29.1892,64.1364);
   cutg->SetPoint(1,27.8805,56.6695);
   cutg->SetPoint(2,26.3202,47.6307);
   cutg->SetPoint(3,25.3136,41.3428);
   cutg->SetPoint(4,23.854,37.8059);
   cutg->SetPoint(5,21.6897,30.732);
   cutg->SetPoint(6,18.7201,23.2652);
   cutg->SetPoint(7,17.1598,21.3002);
   cutg->SetPoint(8,15.3982,18.1562);
   cutg->SetPoint(9,13.9386,16.1913);
   cutg->SetPoint(10,12.932,13.4403);
   cutg->SetPoint(11,12.932,5.58049);
   cutg->SetPoint(12,15.2472,8.72443);
   cutg->SetPoint(13,17.4115,13.8333);
   cutg->SetPoint(14,21.2367,18.5492);
   cutg->SetPoint(15,22.948,23.6581);
   cutg->SetPoint(16,25.4143,31.125);
   cutg->SetPoint(17,26.5719,34.2689);
   cutg->SetPoint(18,27.7799,40.1638);
   cutg->SetPoint(19,29.0382,49.2027);
   cutg->SetPoint(20,31.4541,39.7708);
   cutg->SetPoint(21,33.6184,33.483);
   cutg->SetPoint(22,35.3296,26.4091);
   cutg->SetPoint(23,37.4436,21.6932);
   cutg->SetPoint(24,38.9535,17.7633);
   cutg->SetPoint(25,40.9165,14.2263);
   cutg->SetPoint(26,42.4768,12.2614);
   cutg->SetPoint(27,43.8861,12.2614);
   cutg->SetPoint(28,45.094,11.8684);
   cutg->SetPoint(29,45.547,18.5492);
   cutg->SetPoint(30,43.1311,20.1212);
   cutg->SetPoint(31,40.6648,26.0161);
   cutg->SetPoint(32,37.9972,30.732);
   cutg->SetPoint(33,36.286,36.6269);
   cutg->SetPoint(34,34.4237,45.6657);
   cutg->SetPoint(35,32.5614,50.3816);
   cutg->SetPoint(36,31.5044,56.2765);
   cutg->SetPoint(37,30.3971,60.5994);
   cutg->SetPoint(38,29.5415,63.7434);
   cutg->SetPoint(39,29.1892,64.1364);

   return cutg;
}
