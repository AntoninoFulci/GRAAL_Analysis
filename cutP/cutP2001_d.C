TCutG *myProtonForwCut_2001_d(){ 
  // cout<<"Il taglio 2001_d è stato caricato"<<endl;

  TCutG *cutg = new TCutG("CUTG",26);
  cutg->SetVarX("Tof_trf[0]");
  cutg->SetVarY("De_trf[0]");
  cutg->SetTitle("Graph");
  cutg->SetFillStyle(1000);
  cutg->SetPoint(0,12.0062,7.41237);
  cutg->SetPoint(1,11.8417,10.4605);
  cutg->SetPoint(2,13.9221,13.9646);
  cutg->SetPoint(3,16.7444,19.4281);
  cutg->SetPoint(4,18.9312,23.8213);
  cutg->SetPoint(5,21.9568,30.1885);
  cutg->SetPoint(6,25.455,41.5304);
  cutg->SetPoint(7,28.3817,59.6592);
  cutg->SetPoint(8,28.8695,61.3976);
  cutg->SetPoint(9,31.0646,50.4706);
  cutg->SetPoint(10,36.7439,31.1001);
  cutg->SetPoint(11,42.7716,19.6764);
  cutg->SetPoint(12,50.9944,8.99777);
  cutg->SetPoint(13,49.1826,8.0044);
  cutg->SetPoint(14,45.0363,11.7295);
  cutg->SetPoint(15,40.5068,16.9447);
  cutg->SetPoint(16,36.2212,25.8849);
  cutg->SetPoint(17,31.9356,38.5503);
  cutg->SetPoint(18,29.9845,46.7455);
  cutg->SetPoint(19,29.0172,49.2019);
  cutg->SetPoint(20,28.2109,45.5442);
  cutg->SetPoint(21,27.059,36.2475);
  cutg->SetPoint(22,24.2006,27.6233);
  cutg->SetPoint(23,18.382,16.1996);
  cutg->SetPoint(24,13.1556,8.50108);
  cutg->SetPoint(25,12.0062,7.41237);
  return cutg;
}
