TCutG *myProtonForwCut_2002_uv2(){ 
   // cout<<"Il taglio 2002_uv2 è stato caricato"<<endl;
   
   TCutG *cutg = new TCutG("CUTG",29);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.5332,6.84697);
   cutg->SetPoint(1,11.3049,10.0297);
   cutg->SetPoint(2,16.9605,19.3768);
   cutg->SetPoint(3,20.6674,27.6184);
   cutg->SetPoint(4,22.3115,32.9787);
   cutg->SetPoint(5,24.3667,40.1817);
   cutg->SetPoint(6,25.8282,45.7096);
   cutg->SetPoint(7,27.4267,55.5928);
   cutg->SetPoint(8,28.2031,60.7856);
   cutg->SetPoint(9,28.7055,62.1257);
   cutg->SetPoint(10,28.9795,62.7958);
   cutg->SetPoint(11,29.9386,58.608);
   cutg->SetPoint(12,32.1764,47.8872);
   cutg->SetPoint(13,35.4191,35.4914);
   cutg->SetPoint(14,39.6208,25.9433);
   cutg->SetPoint(15,44.2792,17.5677);
   cutg->SetPoint(16,48.0242,12.2073);
   cutg->SetPoint(17,51.2669,9.19213);
   cutg->SetPoint(18,48.2983,9.52715);
   cutg->SetPoint(19,42.7264,15.39);
   cutg->SetPoint(20,39.1184,21.0854);
   cutg->SetPoint(21,34.0033,33.3138);
   cutg->SetPoint(22,31.126,43.867);
   cutg->SetPoint(23,29.2535,52.5776);
   cutg->SetPoint(24,28.2944,47.8872);
   cutg->SetPoint(25,26.6503,37.8366);
   cutg->SetPoint(26,23.4533,26.1108);
   cutg->SetPoint(27,18.1643,15.1053);
   cutg->SetPoint(28,11.5332,6.84697);

   return cutg;
}
