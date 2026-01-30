TCutG *myPionCentrCut_2006_d(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2006_d",28);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0280917,1.31944);
   cutg->SetPoint(1,0.0484212,2.62153);
   cutg->SetPoint(2,0.0853839,1.97049);
   cutg->SetPoint(3,0.114954,1.71007);
   cutg->SetPoint(4,0.175943,1.71007);
   cutg->SetPoint(5,0.26835,1.71007);
   cutg->SetPoint(6,0.331186,1.71007);
   cutg->SetPoint(7,0.349668,1.97049);
   cutg->SetPoint(8,0.353364,2.44792);
   cutg->SetPoint(9,0.308682,2.83854);
   cutg->SetPoint(10,0.29235,2.92535);
   cutg->SetPoint(11,0.259685,3.22917);
   cutg->SetPoint(12,0.214771,3.40278);
   cutg->SetPoint(13,0.165774,3.40278);
   cutg->SetPoint(14,0.114954,3.83681);
   cutg->SetPoint(15,0.0816877,4.22743);
   cutg->SetPoint(16,0.05951,5.22569);
   cutg->SetPoint(17,0.0521175,6.05035);
   cutg->SetPoint(18,0.0391805,7.09201);
   cutg->SetPoint(19,0.0243954,8.00347);
   cutg->SetPoint(20,0.0133066,8.95833);
   cutg->SetPoint(21,0.018851,6.70139);
   cutg->SetPoint(22,0.0170029,3.96701);
   cutg->SetPoint(23,0.0170029,2.27431);
   cutg->SetPoint(24,0.0170029,0.755208);
   cutg->SetPoint(25,0.0225473,0.798611);
   cutg->SetPoint(26,0.0170029,0.885417);
   cutg->SetPoint(27,0.0280917,1.31944);
   
   return cutg;
}
