TCutG* ProtonCntCut_2003_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("ProtonCntCut_2003_vis",21);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.161605,3.7066);
   cutg->SetPoint(1,0.12937,4.83507);
   cutg->SetPoint(2,0.0713467,7.13542);
   cutg->SetPoint(3,0.0455587,8.61111);
   cutg->SetPoint(4,0.0262178,10.1736);
   cutg->SetPoint(5,0.0154728,13.125);
   cutg->SetPoint(6,0.0176218,14.8611);
   cutg->SetPoint(7,0.0176218,17.0747);
   cutg->SetPoint(8,0.0176218,17.9861);
   cutg->SetPoint(9,0.0219198,18.6372);
   cutg->SetPoint(10,0.0498567,18.4635);
   cutg->SetPoint(11,0.0520057,15.1215);
   cutg->SetPoint(12,0.0606017,12.908);
   cutg->SetPoint(13,0.0863897,9.78299);
   cutg->SetPoint(14,0.133668,7.56944);
   cutg->SetPoint(15,0.226074,5.44271);
   cutg->SetPoint(16,0.322779,4.27083);
   cutg->SetPoint(17,0.262607,3.05556);
   cutg->SetPoint(18,0.21533,3.09896);
   cutg->SetPoint(19,0.174499,3.44618);
   cutg->SetPoint(20,0.161605,3.7066);
   
   return cutg;
}
