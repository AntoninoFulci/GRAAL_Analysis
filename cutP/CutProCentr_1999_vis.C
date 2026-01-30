TCutG *myProtonCentrCut_1999_vis(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_1999_vis",26);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.133668,4.66146);
   cutg->SetPoint(1,0.127221,4.83507);
   cutg->SetPoint(2,0.103582,5.87674);
   cutg->SetPoint(3,0.0820917,6.875);
   cutg->SetPoint(4,0.0563037,8.13368);
   cutg->SetPoint(5,0.0455587,10.0434);
   cutg->SetPoint(6,0.0305158,11.3455);
   cutg->SetPoint(7,0.0219198,12.9948);
   cutg->SetPoint(8,0.0133238,14.2969);
   cutg->SetPoint(9,0.0111748,16.3368);
   cutg->SetPoint(10,0.0133238,17.6389);
   cutg->SetPoint(11,0.0197708,18.5938);
   cutg->SetPoint(12,0.0326647,18.5069);
   cutg->SetPoint(13,0.0369627,15.7726);
   cutg->SetPoint(14,0.0520057,13.125);
   cutg->SetPoint(15,0.0691977,11.2587);
   cutg->SetPoint(16,0.10788,9.08854);
   cutg->SetPoint(17,0.133668,8.00347);
   cutg->SetPoint(18,0.178797,6.57118);
   cutg->SetPoint(19,0.247564,5.65972);
   cutg->SetPoint(20,0.318481,4.66146);
   cutg->SetPoint(21,0.264756,3.83681);
   cutg->SetPoint(22,0.211032,3.96701);
   cutg->SetPoint(23,0.157307,4.40104);
   cutg->SetPoint(24,0.153009,4.40104);
   cutg->SetPoint(25,0.133668,4.66146);
   
   
   return cutg;
}
