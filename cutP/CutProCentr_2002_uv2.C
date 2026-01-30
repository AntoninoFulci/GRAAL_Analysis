TCutG *myProtonCentrCut_2002_uv2(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2002_uv2",33);
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
   cutg->SetPoint(11,0.178797,7.26562);
   cutg->SetPoint(12,0.195989,6.74479);
   cutg->SetPoint(13,0.238968,5.83333);
   cutg->SetPoint(14,0.309885,5.00868);
   cutg->SetPoint(15,0.378653,4.01042);
   cutg->SetPoint(16,0.42808,3.88021);
   cutg->SetPoint(17,0.458166,3.7066);
   cutg->SetPoint(18,0.453868,3.14236);
   cutg->SetPoint(19,0.456017,2.70833);
   cutg->SetPoint(20,0.443123,2.53472);
   cutg->SetPoint(21,0.410888,2.70833);
   cutg->SetPoint(22,0.335673,3.01215);
   cutg->SetPoint(23,0.27765,3.22917);
   cutg->SetPoint(24,0.232521,3.53299);
   cutg->SetPoint(25,0.174499,3.92361);
   cutg->SetPoint(26,0.142264,4.57465);
   cutg->SetPoint(27,0.0971347,5.78993);
   cutg->SetPoint(28,0.0713467,6.61458);
   cutg->SetPoint(29,0.0498567,7.56944);
   cutg->SetPoint(30,0.0326647,8.26389);
   cutg->SetPoint(31,0.00902578,9.65278);
   cutg->SetPoint(32,0.00902578,12.1267);
   
   return cutg;
}
