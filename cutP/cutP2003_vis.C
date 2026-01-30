TCutG *myProtonForwCut_2003_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CutForwPro_2003_vis",41);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,28.7367,62.3802);
   cutg->SetPoint(1,27.708,59.099);
   cutg->SetPoint(2,27.365,53.6302);
   cutg->SetPoint(3,25.8562,46.3385);
   cutg->SetPoint(4,24.9646,41.0521);
   cutg->SetPoint(5,22.7013,33.7604);
   cutg->SetPoint(6,20.5066,29.2031);
   cutg->SetPoint(7,18.1748,23.7344);
   cutg->SetPoint(8,16.2544,19.9062);
   cutg->SetPoint(9,14.7456,16.9896);
   cutg->SetPoint(10,14.1969,15.349);
   cutg->SetPoint(11,11.6593,11.7031);
   cutg->SetPoint(12,11.2478,9.88021);
   cutg->SetPoint(13,11.2478,4.59375);
   cutg->SetPoint(14,14.6084,8.23958);
   cutg->SetPoint(15,18.7235,15.1667);
   cutg->SetPoint(16,21.3982,20.2708);
   cutg->SetPoint(17,23.8673,24.099);
   cutg->SetPoint(18,25.7876,30.6615);
   cutg->SetPoint(19,27.4336,38.1354);
   cutg->SetPoint(20,28.4624,42.875);
   cutg->SetPoint(21,29.4226,47.25);
   cutg->SetPoint(22,30.5885,43.0573);
   cutg->SetPoint(23,31.5487,37.7708);
   cutg->SetPoint(24,34.2235,32.3021);
   cutg->SetPoint(25,36.2124,27.3802);
   cutg->SetPoint(26,38.75,21.9115);
   cutg->SetPoint(27,41.0819,18.0833);
   cutg->SetPoint(28,43.8938,13.3437);
   cutg->SetPoint(29,46.0199,10.974);
   cutg->SetPoint(30,50.6836,11.1562);
   cutg->SetPoint(31,46.1571,17.1719);
   cutg->SetPoint(32,43.1394,21.9115);
   cutg->SetPoint(33,40.3274,25.9219);
   cutg->SetPoint(34,36.7611,34.8542);
   cutg->SetPoint(35,33.8805,43.2396);
   cutg->SetPoint(36,31.823,51.625);
   cutg->SetPoint(37,31.0686,56.1823);
   cutg->SetPoint(38,29.8341,60.5573);
   cutg->SetPoint(39,28.8053,62.1979);
   cutg->SetPoint(40,28.7367,62.3802);

   return cutg;
}
