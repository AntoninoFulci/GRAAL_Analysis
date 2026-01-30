TCutG *myProtonCentrCut_2002_d1(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2002_d1",33);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("De_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetLineColor(2);
   cutg->SetPoint(0,0.00902578,12.1267);
   cutg->SetPoint(1,0.0111748,13.6024);
   cutg->SetPoint(2,0.0154728,14.3837);
   cutg->SetPoint(3,0.0133238,15.2517);
   cutg->SetPoint(4,0.0133238,16.3802);
   cutg->SetPoint(5,0.0154728,20.0694);
   cutg->SetPoint(6,0.0326647,19.9826);
   cutg->SetPoint(7,0.0498567,14.6007);
   cutg->SetPoint(8,0.0498567,13.8628);
   cutg->SetPoint(9,0.0648997,11.4757);
   cutg->SetPoint(10,0.0971347,9.08854);
   cutg->SetPoint(11,0.15086,7.00521);
   cutg->SetPoint(12,0.17235,6.61458);
   cutg->SetPoint(13,0.221776,5.74653);
   cutg->SetPoint(14,0.301289,4.53125);
   cutg->SetPoint(15,0.378653,4.01042);
   cutg->SetPoint(16,0.402292,3.96701);
   cutg->SetPoint(17,0.413037,3.44618);
   cutg->SetPoint(18,0.40659,3.22917);
   cutg->SetPoint(19,0.40659,3.05556);
   cutg->SetPoint(20,0.402292,3.05556);
   cutg->SetPoint(21,0.410888,2.92535);
   cutg->SetPoint(22,0.335673,3.01215);
   cutg->SetPoint(23,0.286246,2.92535);
   cutg->SetPoint(24,0.232521,3.14236);
   cutg->SetPoint(25,0.200287,3.40278);
   cutg->SetPoint(26,0.137966,4.44444);
   cutg->SetPoint(27,0.0799427,5.74653);
   cutg->SetPoint(28,0.0563037,6.39757);
   cutg->SetPoint(29,0.0305158,7.30903);
   cutg->SetPoint(30,0.0133238,8.26389);
   cutg->SetPoint(31,0.00902578,9.65278);
   cutg->SetPoint(32,0.00902578,12.1267);
   
   return cutg;
}
