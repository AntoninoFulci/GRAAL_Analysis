TCutG* ProtonCntCut_2002_d3(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("ProtonCntCut_2002_d3",23);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.112178,4.87847);
   cutg->SetPoint(1,0.0842407,6.00694);
   cutg->SetPoint(2,0.0691977,7.43924);
   cutg->SetPoint(3,0.0455587,9.00174);
   cutg->SetPoint(4,0.0283668,10.9115);
   cutg->SetPoint(5,0.0240688,13.559);
   cutg->SetPoint(6,0.0154728,14.8611);
   cutg->SetPoint(7,0.0154728,16.8142);
   cutg->SetPoint(8,0.0133238,18.2465);
   cutg->SetPoint(9,0.0197708,19.2448);
   cutg->SetPoint(10,0.0391117,19.2448);
   cutg->SetPoint(11,0.0412607,15.4688);
   cutg->SetPoint(12,0.0734957,11.4757);
   cutg->SetPoint(13,0.122923,8.17708);
   cutg->SetPoint(14,0.180946,6.52778);
   cutg->SetPoint(15,0.266905,5.22569);
   cutg->SetPoint(16,0.339971,4.48785);
   cutg->SetPoint(17,0.346418,3.27257);
   cutg->SetPoint(18,0.258309,3.09896);
   cutg->SetPoint(19,0.204585,3.35937);
   cutg->SetPoint(20,0.185244,3.75);
   cutg->SetPoint(21,0.116476,4.83507);
   cutg->SetPoint(22,0.112178,4.87847);
     
   return cutg;
   
}
