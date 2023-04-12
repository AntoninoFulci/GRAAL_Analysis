TCutG *myProtonForwCut_2002_vis1(){ 
   // cout<<"Il taglio 2002_vis1 è stato caricato"<<endl;
   
   TCutG *cutg = new TCutG("CUTG",33);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.417,6.61444);
   cutg->SetPoint(1,11.0642,9.7743);
   cutg->SetPoint(2,15.0782,15.9674);
   cutg->SetPoint(3,18.9393,23.7624);
   cutg->SetPoint(4,21.3342,29.0827);
   cutg->SetPoint(5,23.9734,37.0014);
   cutg->SetPoint(6,26.5027,46.9283);
   cutg->SetPoint(7,27.5291,54.9897);
   cutg->SetPoint(8,28.14,60.4338);
   cutg->SetPoint(9,28.9465,60.9573);
   cutg->SetPoint(10,29.2031,59.0252);
   cutg->SetPoint(11,29.9362,54.4472);
   cutg->SetPoint(12,31.3536,48.137);
   cutg->SetPoint(13,32.9664,40.9607);
   cutg->SetPoint(14,35.459,32.4234);
   cutg->SetPoint(15,38.2449,25.742);
   cutg->SetPoint(16,44.061,16.2149);
   cutg->SetPoint(17,47.7755,10.3996);
   cutg->SetPoint(18,52.9563,7.05892);
   cutg->SetPoint(19,52.2232,5.57417);
   cutg->SetPoint(20,47.58,8.17248);
   cutg->SetPoint(21,43.3279,13.7403);
   cutg->SetPoint(22,39.4179,20.1742);
   cutg->SetPoint(23,35.3613,28.5878);
   cutg->SetPoint(24,33.4552,33.2895);
   cutg->SetPoint(25,31.2069,41.8268);
   cutg->SetPoint(26,29.0724,50.5761);
   cutg->SetPoint(27,28.4917,49.8129);
   cutg->SetPoint(28,27.8346,44.4251);
   cutg->SetPoint(29,25.9284,35.1454);
   cutg->SetPoint(30,23.0937,25.4946);
   cutg->SetPoint(31,19.0782,17.16);
   cutg->SetPoint(32,11.417,6.61444);

   return cutg;
}
