TCutG *myProtonForwCut_2002_vis2(){ 
   // cout<<"Il taglio 2002_vis2 è stato caricato"<<endl;

   
   TCutG *cutg = new TCutG("CUTG",29);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.6523,6.61876);
   cutg->SetPoint(1,11.4613,10.5055);
   cutg->SetPoint(2,15.0888,16.974);
   cutg->SetPoint(3,19.947,27.1643);
   cutg->SetPoint(4,22.5598,33.5659);
   cutg->SetPoint(5,24.9276,41.1434);
   cutg->SetPoint(6,26.6831,48.8514);
   cutg->SetPoint(7,27.9079,57.6046);
   cutg->SetPoint(8,28.2753,60.7401);
   cutg->SetPoint(9,29.2143,60.3482);
   cutg->SetPoint(10,30.9289,51.595);
   cutg->SetPoint(11,33.0926,41.9272);
   cutg->SetPoint(12,36.6036,31.345);
   cutg->SetPoint(13,41.6659,20.8934);
   cutg->SetPoint(14,46.7282,14.0998);
   cutg->SetPoint(15,50.7699,9.52725);
   cutg->SetPoint(16,49.3002,9.13531);
   cutg->SetPoint(17,44.442,13.5772);
   cutg->SetPoint(18,40.1962,19.8482);
   cutg->SetPoint(19,35.5013,29.2547);
   cutg->SetPoint(20,33.2151,36.5708);
   cutg->SetPoint(21,29.3776,50.1579);
   cutg->SetPoint(22,28.6835,50.1579);
   cutg->SetPoint(23,28.3569,46.6305);
   cutg->SetPoint(24,26.4382,35.395);
   cutg->SetPoint(25,23.6621,26.5111);
   cutg->SetPoint(26,19.7429,17.366);
   cutg->SetPoint(27,12.8435,7.82886);
   cutg->SetPoint(28,11.6523,6.61876);

   return cutg;
}
