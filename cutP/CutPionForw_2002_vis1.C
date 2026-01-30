TCutG *myPionForwCut_2002_vis1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTForwPion2002_vis1",10);
   cutg->SetVarX("Tof_trf");
   cutg->SetVarY("De_trf");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,8.42478,7.93681);
   cutg->SetPoint(1,9.34513,11.6456);
   cutg->SetPoint(2,10.6195,10.9038);
   cutg->SetPoint(3,11.0442,9.42033);
   cutg->SetPoint(4,11.1858,6.08242);
   cutg->SetPoint(5,9.9823,4.22802);
   cutg->SetPoint(6,9.48673,4.22802);
   cutg->SetPoint(7,8.28319,5.34066);
   cutg->SetPoint(8,8.56637,9.04945);
   cutg->SetPoint(9,8.42478,7.93681);
   
   return cutg;
}
