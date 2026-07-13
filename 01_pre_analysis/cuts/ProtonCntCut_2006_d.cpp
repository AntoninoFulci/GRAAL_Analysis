TCutG* ProtonCntCut_2006_d(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("ProtonCntCut_2006_d",28);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.194269,4.04514);
   cutg->SetPoint(1,0.144305,5.15104);
   cutg->SetPoint(2,0.11033,6.21441);
   cutg->SetPoint(3,0.0823496,7.27778);
   cutg->SetPoint(4,0.0503725,9.36198);
   cutg->SetPoint(5,0.0363825,11.276);
   cutg->SetPoint(6,0.0263897,13.3177);
   cutg->SetPoint(7,0.0183954,14.4661);
   cutg->SetPoint(8,0.0163968,16.0399);
   cutg->SetPoint(9,0.0163968,18.0391);
   cutg->SetPoint(10,0.00840257,19.23);
   cutg->SetPoint(11,0.0143983,19.8681);
   cutg->SetPoint(12,0.0343839,19.6979);
   cutg->SetPoint(13,0.0483739,16.9332);
   cutg->SetPoint(14,0.0563682,14.5087);
   cutg->SetPoint(15,0.0823496,11.7865);
   cutg->SetPoint(16,0.100337,10.1701);
   cutg->SetPoint(17,0.136311,8.29861);
   cutg->SetPoint(18,0.196268,7.02257);
   cutg->SetPoint(19,0.244234,5.91667);
   cutg->SetPoint(20,0.312185,4.72569);
   cutg->SetPoint(21,0.44409,3.875);
   cutg->SetPoint(22,0.496053,2.85417);
   cutg->SetPoint(23,0.364148,2.93924);
   cutg->SetPoint(24,0.286203,3.27951);
   cutg->SetPoint(25,0.226246,3.66233);
   cutg->SetPoint(26,0.198266,3.96007);
   cutg->SetPoint(27,0.194269,4.04514);
   
   return cutg;
}
