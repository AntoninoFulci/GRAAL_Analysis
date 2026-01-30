TCutG *myProtonCentrCut_2000_vis(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2000_vis",23);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0891126,5.73486);
   cutg->SetPoint(1,0.0546015,8.0613);
   cutg->SetPoint(2,0.0324158,9.61226);
   cutg->SetPoint(3,0.0225555,11.4586);
   cutg->SetPoint(4,0.0102301,13.6374);
   cutg->SetPoint(5,0.0114626,15.4099);
   cutg->SetPoint(6,0.00899753,18.3272);
   cutg->SetPoint(7,0.0262531,18.2903);
   cutg->SetPoint(8,0.0324158,16.4808);
   cutg->SetPoint(9,0.0348808,14.5606);
   cutg->SetPoint(10,0.0521364,13.0465);
   cutg->SetPoint(11,0.055834,12.1233);
   cutg->SetPoint(12,0.0669269,10.9417);
   cutg->SetPoint(13,0.0915776,9.64919);
   cutg->SetPoint(14,0.129786,7.61817);
   cutg->SetPoint(15,0.171693,6.21492);
   cutg->SetPoint(16,0.250575,4.44239);
   cutg->SetPoint(17,0.293714,3.55613);
   cutg->SetPoint(18,0.197576,3.55613);
   cutg->SetPoint(19,0.166763,3.88848);
   cutg->SetPoint(20,0.119926,4.99631);
   cutg->SetPoint(21,0.0903451,5.661);
   cutg->SetPoint(22,0.0891126,5.73486);
   
   return cutg;
}
