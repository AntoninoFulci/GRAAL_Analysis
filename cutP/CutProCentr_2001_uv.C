TCutG *myProtonCentrCut_2001_uv(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2001_uv",24);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.103582,5.39931);
   cutg->SetPoint(1,0.0863897,6.09375);
   cutg->SetPoint(2,0.0691977,7.30903);
   cutg->SetPoint(3,0.0520057,8.74132);
   cutg->SetPoint(4,0.0326647,10.9549);
   cutg->SetPoint(5,0.0133238,11.9965);
   cutg->SetPoint(6,0.0176218,15.0781);
   cutg->SetPoint(7,0.0133238,17.7691);
   cutg->SetPoint(8,0.0176218,19.2014);
   cutg->SetPoint(9,0.0391117,18.941);
   cutg->SetPoint(10,0.0477077,15.2517);
   cutg->SetPoint(11,0.0541547,13.0816);
   cutg->SetPoint(12,0.103582,10.0868);
   cutg->SetPoint(13,0.163754,6.39757);
   cutg->SetPoint(14,0.258309,4.87847);
   cutg->SetPoint(15,0.288395,4.09722);
   cutg->SetPoint(16,0.27765,3.31597);
   cutg->SetPoint(17,0.247564,3.14236);
   cutg->SetPoint(18,0.217479,3.05556);
   cutg->SetPoint(19,0.180946,3.44618);
   cutg->SetPoint(20,0.140115,4.44444);
   cutg->SetPoint(21,0.12937,4.70486);
   cutg->SetPoint(22,0.127221,4.70486);
   cutg->SetPoint(23,0.103582,5.39931);
   
   return cutg;
}
