TCutG* ProtonCntCut_2000_uv1(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
  TCutG *cutg = new TCutG("ProtonCntCut_2000_uv1",25);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.174499,4.09722);
   cutg->SetPoint(1,0.116476,5.52951);
   cutg->SetPoint(2,0.0863897,6.78819);
   cutg->SetPoint(3,0.0541547,8.52431);
   cutg->SetPoint(4,0.0391117,10.3038);
   cutg->SetPoint(5,0.0197708,13.0382);
   cutg->SetPoint(6,0.0133238,14.3403);
   cutg->SetPoint(7,0.0133238,15.9462);
   cutg->SetPoint(8,0.0176218,18.1163);
   cutg->SetPoint(9,0.0176218,18.8976);
   cutg->SetPoint(10,0.0455587,18.941);
   cutg->SetPoint(11,0.0434097,15.9028);
   cutg->SetPoint(12,0.0477077,13.2552);
   cutg->SetPoint(13,0.0842407,10.3472);
   cutg->SetPoint(14,0.0906877,9.69618);
   cutg->SetPoint(15,0.135817,7.43924);
   cutg->SetPoint(16,0.185244,5.87674);
   cutg->SetPoint(17,0.245415,4.87847);
   cutg->SetPoint(18,0.309885,4.27083);
   cutg->SetPoint(19,0.335673,3.88021);
   cutg->SetPoint(20,0.296991,3.53299);
   cutg->SetPoint(21,0.266905,3.35937);
   cutg->SetPoint(22,0.213181,3.61979);
   cutg->SetPoint(23,0.180946,4.05382);
   cutg->SetPoint(24,0.174499,4.09722);
   
   return cutg;
}
