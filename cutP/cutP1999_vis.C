TCutG *myProtonForwCut_1999_vis(){ 
   // cout<<"Il taglio 1999_vis è stato caricato"<<endl;
   
   TCutG *cutg = new TCutG("CUTG",37);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.9622,114.124);
   cutg->SetPoint(1,11.7844,148.644);
   cutg->SetPoint(2,13.5616,194.671);
   cutg->SetPoint(3,15.4276,242.342);
   cutg->SetPoint(4,18.0045,309.739);
   cutg->SetPoint(5,21.233,433.025);
   cutg->SetPoint(6,23.7506,549.737);
   cutg->SetPoint(7,25.7055,714.119);
   cutg->SetPoint(8,27.3938,916.309);
   cutg->SetPoint(9,27.9861,986.993);
   cutg->SetPoint(10,28.6081,1019.87);
   cutg->SetPoint(11,29.7633,972.199);
   cutg->SetPoint(12,31.3035,863.707);
   cutg->SetPoint(13,32.9325,735.489);
   cutg->SetPoint(14,35.4798,569.463);
   cutg->SetPoint(15,38.4417,442.888);
   cutg->SetPoint(16,42.2033,332.752);
   cutg->SetPoint(17,46.7351,240.698);
   cutg->SetPoint(18,51.7999,156.863);
   cutg->SetPoint(19,50.4375,143.713);
   cutg->SetPoint(20,46.9424,160.151);
   cutg->SetPoint(21,43.1808,237.411);
   cutg->SetPoint(22,38.3232,342.615);
   cutg->SetPoint(23,34.8874,436.313);
   cutg->SetPoint(24,33.1695,528.367);
   cutg->SetPoint(25,30.9184,630.284);
   cutg->SetPoint(26,29.7633,648.366);
   cutg->SetPoint(27,28.5785,650.01);
   cutg->SetPoint(28,27.8973,630.284);
   cutg->SetPoint(29,26.7717,536.586);
   cutg->SetPoint(30,24.6095,444.532);
   cutg->SetPoint(31,22.8028,360.697);
   cutg->SetPoint(32,19.752,273.575);
   cutg->SetPoint(33,16.3754,197.959);
   cutg->SetPoint(34,13.6505,143.713);
   cutg->SetPoint(35,12.7323,125.631);
   cutg->SetPoint(36,11.9622,114.124);
   return cutg;
}

