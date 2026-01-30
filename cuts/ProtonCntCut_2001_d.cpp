TCutG* ProtonCntCut_2001_d(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("ProtonCntCut_2001_d",33);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
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
   cutg->SetPoint(11,0.142264,7.69965);
   cutg->SetPoint(12,0.178797,6.70139);
   cutg->SetPoint(13,0.223925,5.65972);
   cutg->SetPoint(14,0.296991,4.31424);
   cutg->SetPoint(15,0.296991,4.27083);
   cutg->SetPoint(16,0.303438,4.27083);
   cutg->SetPoint(17,0.296991,4.27083);
   cutg->SetPoint(18,0.305587,4.05382);
   cutg->SetPoint(19,0.305587,3.96701);
   cutg->SetPoint(20,0.324928,3.53299);
   cutg->SetPoint(21,0.357163,3.09896);
   cutg->SetPoint(22,0.318481,2.96875);
   cutg->SetPoint(23,0.286246,2.92535);
   cutg->SetPoint(24,0.226074,3.01215);
   cutg->SetPoint(25,0.176648,3.40278);
   cutg->SetPoint(26,0.135817,4.18403);
   cutg->SetPoint(27,0.0777937,5.74653);
   cutg->SetPoint(28,0.0498567,6.8316);
   cutg->SetPoint(29,0.0477077,7.30903);
   cutg->SetPoint(30,0.0391117,8.09028);
   cutg->SetPoint(31,0.0262178,9.52257);
   cutg->SetPoint(32,0.00902578,12.1267);
   
   return cutg;
}
