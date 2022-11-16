TCutG *myProtonCentrCut_1999_d1(){
   
   TCutG *cutg = new TCutG("CUTG",39);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.9921,9.79345);
   cutg->SetPoint(1,14.9256,15.2391);
   cutg->SetPoint(2,17.2902,18.8696);
   cutg->SetPoint(3,20.0637,24.4666);
   cutg->SetPoint(4,22.0905,30.0635);
   cutg->SetPoint(5,24.544,36.2656);
   cutg->SetPoint(6,26.1974,42.4676);
   cutg->SetPoint(7,27.6908,50.6361);
   cutg->SetPoint(8,28.1175,55.3255);
   cutg->SetPoint(9,28.8643,60.9224);
   cutg->SetPoint(10,29.7176,62.1326);
   cutg->SetPoint(11,30.9444,58.8047);
   cutg->SetPoint(12,32.9712,48.0645);
   cutg->SetPoint(13,35.6914,38.8371);
   cutg->SetPoint(14,38.8916,30.3661);
   cutg->SetPoint(15,42.1984,23.1051);
   cutg->SetPoint(16,46.8387,14.6341);
   cutg->SetPoint(17,51.159,10.8523);
   cutg->SetPoint(18,53.1858,7.82695);
   cutg->SetPoint(19,50.1456,8.28076);
   cutg->SetPoint(20,45.5053,13.4239);
   cutg->SetPoint(21,41.9318,19.3234);
   cutg->SetPoint(22,38.5715,25.0716);
   cutg->SetPoint(23,35.478,33.3914);
   cutg->SetPoint(24,33.0779,40.1986);
   cutg->SetPoint(25,31.3711,47.1569);
   cutg->SetPoint(26,30.3577,50.7874);
   cutg->SetPoint(27,29.771,52.7539);
   cutg->SetPoint(28,29.3976,51.3925);
   cutg->SetPoint(29,28.8643,46.8544);
   cutg->SetPoint(30,27.3708,38.8371);
   cutg->SetPoint(31,25.6107,32.1813);
   cutg->SetPoint(32,23.2106,25.0716);
   cutg->SetPoint(33,20.9171,19.6259);
   cutg->SetPoint(34,17.5569,14.1803);
   cutg->SetPoint(35,14.6767,9.94472);
   cutg->SetPoint(36,12.9699,7.97822);
   cutg->SetPoint(37,11.7965,6.54117);
   cutg->SetPoint(38,11.9921,9.79345);
   
   return cutg;
}
