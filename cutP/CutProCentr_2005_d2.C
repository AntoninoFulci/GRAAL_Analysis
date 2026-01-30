TCutG* myProtonCentrCut_2005_d2(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2005_d2",27);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.24811,2.82374);
   cutg->SetPoint(1,0.283854,3.14748);
   cutg->SetPoint(2,0.302342,3.47122);
   cutg->SetPoint(3,0.282621,4.04676);
   cutg->SetPoint(4,0.251808,4.40647);
   cutg->SetPoint(5,0.211134,5.1259);
   cutg->SetPoint(6,0.161832,6.13309);
   cutg->SetPoint(7,0.128554,7.32014);
   cutg->SetPoint(8,0.103903,8.50719);
   cutg->SetPoint(9,0.0804848,10.0899);
   cutg->SetPoint(10,0.0632292,11.4568);
   cutg->SetPoint(11,0.0509039,12.6799);
   cutg->SetPoint(12,0.0410435,14.4065);
   cutg->SetPoint(13,0.0348808,16.0252);
   cutg->SetPoint(14,0.0262531,18.6511);
   cutg->SetPoint(15,0.00899753,18.795);
   cutg->SetPoint(16,0.0114626,16.0971);
   cutg->SetPoint(17,0.0139277,13.759);
   cutg->SetPoint(18,0.0139277,10.8453);
   cutg->SetPoint(19,0.0151602,8.47122);
   cutg->SetPoint(20,0.039811,7.21223);
   cutg->SetPoint(21,0.0521364,6.52878);
   cutg->SetPoint(22,0.0792523,5.44964);
   cutg->SetPoint(23,0.156902,4.01079);
   cutg->SetPoint(24,0.24811,2.82374);
   cutg->SetPoint(25,0.262901,2.93165);
   cutg->SetPoint(26,0.24811,2.82374);
   
   return cutg;
}
