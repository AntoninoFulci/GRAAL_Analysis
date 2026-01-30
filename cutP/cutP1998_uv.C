TCutG *myProtonForwCut_1998_uv(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *cutg = new TCutG("Cut_ForwPro_1998_uv",41);
   cutg->SetVarX("TOF(ns)");
   cutg->SetVarY("DE/dx(MeV)");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,28.8739,1120.38);
   cutg->SetPoint(1,27.5022,1094.24);
   cutg->SetPoint(2,26.1305,854.659);
   cutg->SetPoint(3,24.5531,723.977);
   cutg->SetPoint(4,23.1814,632.5);
   cutg->SetPoint(5,21.604,536.667);
   cutg->SetPoint(6,19.4093,449.545);
   cutg->SetPoint(7,17.0088,327.576);
   cutg->SetPoint(8,14.8827,284.015);
   cutg->SetPoint(9,14.8827,284.015);
   cutg->SetPoint(10,12.3451,218.674);
   cutg->SetPoint(11,11.7965,205.606);
   cutg->SetPoint(12,12.0708,109.773);
   cutg->SetPoint(13,14.1969,153.333);
   cutg->SetPoint(14,16.9403,196.894);
   cutg->SetPoint(15,21.1239,340.644);
   cutg->SetPoint(16,24.2102,453.902);
   cutg->SetPoint(17,26.1991,571.515);
   cutg->SetPoint(18,27.9823,689.129);
   cutg->SetPoint(19,28.7367,784.962);
   cutg->SetPoint(20,29.354,845.947);
   cutg->SetPoint(21,31.823,658.636);
   cutg->SetPoint(22,34.5664,519.242);
   cutg->SetPoint(23,37.3783,388.561);
   cutg->SetPoint(24,40.0531,288.371);
   cutg->SetPoint(25,42.865,218.674);
   cutg->SetPoint(26,45.3341,170.758);
   cutg->SetPoint(27,48.6261,162.045);
   cutg->SetPoint(28,52.0553,157.689);
   cutg->SetPoint(29,47.1858,253.523);
   cutg->SetPoint(30,43.9624,345);
   cutg->SetPoint(31,41.3562,436.477);
   cutg->SetPoint(32,39.3673,501.818);
   cutg->SetPoint(33,37.2412,602.008);
   cutg->SetPoint(34,35.458,723.977);
   cutg->SetPoint(35,33.0575,867.727);
   cutg->SetPoint(36,31.2058,985.341);
   cutg->SetPoint(37,30.2456,1063.75);
   cutg->SetPoint(38,29.5597,1107.31);
   cutg->SetPoint(39,28.9425,1129.09);
   cutg->SetPoint(40,28.8739,1120.38);

   return cutg;
}
