TCutG *myProtonCentrCut_1998_uv(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06

 TCutG *cutg = new TCutG("CUTCentrPro_1998_uv",26);
 cutg->SetVarX("Eclusc_track");
 cutg->SetVarY("Dedx_track");
 cutg->SetTitle("Graph");
 cutg->SetFillStyle(1000);
 cutg->SetLineColor(2);
 cutg->SetPoint(0,0.217479,3.44618);
 cutg->SetPoint(1,0.170201,4.05382);
 cutg->SetPoint(2,0.120774,5.3125);
 cutg->SetPoint(3,0.0713467,7.09201);
 cutg->SetPoint(4,0.0563037,8.13368);
 cutg->SetPoint(5,0.0305158,9.91319);
 cutg->SetPoint(6,0.0262178,12.1267);
 cutg->SetPoint(7,0.0197708,13.776);
 cutg->SetPoint(8,0.0197708,14.3837);
 cutg->SetPoint(9,0.0133238,15.6424);
 cutg->SetPoint(10,0.0154728,17.3351);
 cutg->SetPoint(11,0.0412607,16.9878);
 cutg->SetPoint(12,0.0391117,15.4688);
 cutg->SetPoint(13,0.0477077,13.4722);
 cutg->SetPoint(14,0.0734957,10.3038);
 cutg->SetPoint(15,0.112178,8.35069);
 cutg->SetPoint(16,0.142264,7.04861);
 cutg->SetPoint(17,0.198138,6.05035);
 cutg->SetPoint(18,0.243266,5.3559);
 cutg->SetPoint(19,0.320829,4.75694);
 cutg->SetPoint(20,0.545647,3.58507);
 cutg->SetPoint(21,0.553582,2.4566);
 cutg->SetPoint(22,0.397531,2.5434);
 cutg->SetPoint(23,0.281948,3.05556);
 cutg->SetPoint(24,0.204585,3.57639);
 cutg->SetPoint(25,0.217479,3.44618);

 return cutg;
}
