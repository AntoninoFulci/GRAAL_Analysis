// taglio energia fascio vs angolo theta del protone sopra la soglia
{
  TCutG *cutg = new TCutG("cutg",22);
  cutg->SetVarX("Energy gamma(GeV)");
  cutg->SetVarY("Theta proton(degree)");
  cutg->SetTitle("Graph");
  cutg->SetFillStyle(1000);
  cutg->SetPoint(0,1.44258,-0.171875);
  cutg->SetPoint(1,1.44196,2.69271);
  cutg->SetPoint(2,1.44917,5.46181);
  cutg->SetPoint(3,1.45606,7.2283);
  cutg->SetPoint(4,1.46515,8.99479);
  cutg->SetPoint(5,1.47988,11.0477);
  cutg->SetPoint(6,1.49586,13.1007);
  cutg->SetPoint(7,1.51529,15.3924);
  cutg->SetPoint(8,1.54256,17.5885);
  cutg->SetPoint(9,1.55979,19.0686);
  cutg->SetPoint(10,1.58048,20.3576);
  cutg->SetPoint(11,1.59928,21.3602);
  cutg->SetPoint(12,1.60336,21.0738);
  cutg->SetPoint(13,1.60242,16.6337);
  cutg->SetPoint(14,1.60304,12.3845);
  cutg->SetPoint(15,1.60304,7.41927);
  cutg->SetPoint(16,1.60398,2.40625);
  cutg->SetPoint(17,1.60367,-0.028646);
  cutg->SetPoint(18,1.52563,0.0668401);
  cutg->SetPoint(19,1.4523,0.0190971);
  cutg->SetPoint(20,1.44196,-0.0763891);
  cutg->SetPoint(21,1.44258,-0.171875);
  cutg->Draw();
}
