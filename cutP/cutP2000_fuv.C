TCutG *myProtonForwCut_2000_fuv(){ 
   // cout<<"Il taglio 2000_fuv è stato caricato"<<endl;
   
   TCutG *cutg = new TCutG("cutP2000_fuv",28);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.9292,7.83291);
   cutg->SetPoint(1,13.1741,8.73347);
   cutg->SetPoint(2,16.5578,12.8206);
   cutg->SetPoint(3,20.9471,19.8172);
   cutg->SetPoint(4,25.1768,31.1088);
   cutg->SetPoint(5,27.7305,41.6384);
   cutg->SetPoint(6,28.9755,52.1679);
   cutg->SetPoint(7,30.412,45.8641);
   cutg->SetPoint(8,32.8061,36.3043);
   cutg->SetPoint(9,37.6263,24.8049);
   cutg->SetPoint(10,41.2654,15.9379);
   cutg->SetPoint(11,45.7345,10.2575);
   cutg->SetPoint(12,48.0808,10.396);
   cutg->SetPoint(13,43.9309,17.8083);
   cutg->SetPoint(14,39.7491,26.1211);
   cutg->SetPoint(15,35.5195,36.997);
   cutg->SetPoint(16,32.9178,46.2797);
   cutg->SetPoint(17,30.1726,57.9176);
   cutg->SetPoint(18,29.3215,62.7489);
   cutg->SetPoint(19,28.4907,62.5835);
   cutg->SetPoint(20,27.5155,55.1438);
   cutg->SetPoint(21,25.9985,44.8935);
   cutg->SetPoint(22,23.1018,33.3256);
   cutg->SetPoint(23,18.9999,23.3502);
   cutg->SetPoint(24,15.0575,15.5223);
   cutg->SetPoint(25,12.8549,12.0586);
   cutg->SetPoint(26,11.7376,10.5346);
   cutg->SetPoint(27,11.9292,7.83291);
   return cutg;
}
