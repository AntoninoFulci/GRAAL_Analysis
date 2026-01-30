TCutG *myProtonCentrCut_2002_vis2(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2002_vis2",33);
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
   cutg->SetPoint(11,0.153009,7.39583);
   cutg->SetPoint(12,0.180946,6.52778);
   cutg->SetPoint(13,0.243266,5.61632);
   cutg->SetPoint(14,0.296991,4.31424);
   cutg->SetPoint(15,0.32063,4.14062);
   cutg->SetPoint(16,0.329226,3.83681);
   cutg->SetPoint(17,0.337754,3.39531);
   cutg->SetPoint(18,0.335673,3.27257);
   cutg->SetPoint(19,0.335734,2.50556);
   cutg->SetPoint(20,0.319573,2.61233);
   cutg->SetPoint(21,0.315533,2.50556);
   cutg->SetPoint(22,0.292693,2.79514);
   cutg->SetPoint(23,0.258971,2.86146);
   cutg->SetPoint(24,0.226074,3.01215);
   cutg->SetPoint(25,0.17235,3.18576);
   cutg->SetPoint(26,0.101433,3.88021);
   cutg->SetPoint(27,0.0563037,5.57292);
   cutg->SetPoint(28,0.0412607,6.39757);
   cutg->SetPoint(29,0.0305158,7.30903);
   cutg->SetPoint(30,0.0133238,8.26389);
   cutg->SetPoint(31,0.00902578,9.65278);
   cutg->SetPoint(32,0.00902578,12.1267);
  
  
   return cutg;
}
