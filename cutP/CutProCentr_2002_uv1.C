TCutG *myProtonCentrCut_2002_uv1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2002_uv1",29);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.131519,3.7066);
   cutg->SetPoint(1,0.226074,3.01215);
   cutg->SetPoint(2,0.376504,2.79514);
   cutg->SetPoint(3,0.378653,3.66319);
   cutg->SetPoint(4,0.339971,4.27083);
   cutg->SetPoint(5,0.275501,5.57292);
   cutg->SetPoint(6,0.213181,6.70139);
   cutg->SetPoint(7,0.17235,8.22049);
   cutg->SetPoint(8,0.137966,9.91319);
   cutg->SetPoint(9,0.133668,11.4323);
   cutg->SetPoint(10,0.125072,12.908);
   cutg->SetPoint(11,0.120774,13.6458);
   cutg->SetPoint(12,0.114327,15.4688);
   cutg->SetPoint(13,0.112178,17.0313);
   cutg->SetPoint(14,0.114327,18.724);
   cutg->SetPoint(15,0.112178,19.4618);
   cutg->SetPoint(16,0.10788,19.9826);
   cutg->SetPoint(17,0.0326647,20.0694);
   cutg->SetPoint(18,0.0133238,19.9826);
   cutg->SetPoint(19,0.0111748,18.3767);
   cutg->SetPoint(20,0.0176218,16.2934);
   cutg->SetPoint(21,0.0154728,15.599);
   cutg->SetPoint(22,0.00902578,13.0382);
   cutg->SetPoint(23,0.0111748,12.1701);
   cutg->SetPoint(24,0.0133238,11.6927);
   cutg->SetPoint(25,0.0133238,9.91319);
   cutg->SetPoint(26,0.0154728,8.00347);
   cutg->SetPoint(27,0.0670487,5.39931);
   cutg->SetPoint(28,0.131519,3.7066);
   
   return cutg;
}
