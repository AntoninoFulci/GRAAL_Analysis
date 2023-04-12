TCutG *myProtonForwCut_2000_vis(){ 
  //  cout<<"Il taglio 2000_vis è stato caricato"<<endl;

   
   TCutG *cutg = new TCutG("CUTG",47);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.8333,6.98578);
   cutg->SetPoint(1,11.9191,10.589);
   cutg->SetPoint(2,13.0342,12.1828);
   cutg->SetPoint(3,15.2502,16.2711);
   cutg->SetPoint(4,17.8522,20.5673);
   cutg->SetPoint(5,20.3684,26.5265);
   cutg->SetPoint(6,22.7131,33.0401);
   cutg->SetPoint(7,24.1285,36.6433);
   cutg->SetPoint(8,25.5009,42.1868);
   cutg->SetPoint(9,26.8162,48.9083);
   cutg->SetPoint(10,27.574,55.1447);
   cutg->SetPoint(11,27.8885,58.1936);
   cutg->SetPoint(12,29.0322,60.2724);
   cutg->SetPoint(13,30.3189,54.8675);
   cutg->SetPoint(14,31.6771,47.7996);
   cutg->SetPoint(15,33.4928,41.771);
   cutg->SetPoint(16,34.9511,36.3662);
   cutg->SetPoint(17,37.067,29.714);
   cutg->SetPoint(18,38.9684,25.1406);
   cutg->SetPoint(19,41.6705,20.5673);
   cutg->SetPoint(20,44.587,15.9939);
   cutg->SetPoint(21,46.7458,12.6678);
   cutg->SetPoint(22,49.6195,9.8961);
   cutg->SetPoint(23,51.6067,7.8173);
   cutg->SetPoint(24,49.3621,8.92599);
   cutg->SetPoint(25,47.0604,10.1733);
   cutg->SetPoint(26,44.587,11.6977);
   cutg->SetPoint(27,42.3281,15.0238);
   cutg->SetPoint(28,40.6125,17.7955);
   cutg->SetPoint(29,37.4244,23.339);
   cutg->SetPoint(30,34.9511,30.2684);
   cutg->SetPoint(31,32.9638,36.3662);
   cutg->SetPoint(32,31.0623,43.4341);
   cutg->SetPoint(33,29.6041,49.6012);
   cutg->SetPoint(34,28.9464,50.2941);
   cutg->SetPoint(35,28.3746,47.1066);
   cutg->SetPoint(36,27.0021,39.1379);
   cutg->SetPoint(37,25.8441,33.5944);
   cutg->SetPoint(38,24.4287,29.714);
   cutg->SetPoint(39,22.2699,23.6162);
   cutg->SetPoint(40,20.0539,18.4885);
   cutg->SetPoint(41,17.8522,14.7466);
   cutg->SetPoint(42,15.9507,11.9749);
   cutg->SetPoint(43,14.1351,9.61893);
   cutg->SetPoint(44,13.0771,7.8173);
   cutg->SetPoint(45,12.591,7.33225);
   cutg->SetPoint(46,11.8333,6.98578);
  return cutg;
}

