TCutG *myProtonCentrCut_2002_vis1(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("CUTCentrPro_2002_vis1",21);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.163754,4.09722);
   cutg->SetPoint(1,0.0992837,6.61458);
   cutg->SetPoint(2,0.0520057,8.56771);
   cutg->SetPoint(3,0.0434097,9.78299);
   cutg->SetPoint(4,0.0197708,11.3889);
   cutg->SetPoint(5,0.0219198,13.342);
   cutg->SetPoint(6,0.0111748,16.033);
   cutg->SetPoint(7,0.0219198,18.2031);
   cutg->SetPoint(8,0.0240688,18.7674);
   cutg->SetPoint(9,0.0326647,18.0729);
   cutg->SetPoint(10,0.0369627,15.4253);
   cutg->SetPoint(11,0.0713467,12.1701);
   cutg->SetPoint(12,0.103582,10);
   cutg->SetPoint(13,0.161605,7.48264);
   cutg->SetPoint(14,0.241117,6.31076);
   cutg->SetPoint(15,0.329226,4.79167);
   cutg->SetPoint(16,0.333524,3.7934);
   cutg->SetPoint(17,0.271203,3.48958);
   cutg->SetPoint(18,0.198138,3.83681);
   cutg->SetPoint(19,0.159456,4.27083);
   cutg->SetPoint(20,0.163754,4.09722);
   
   return cutg;
}
