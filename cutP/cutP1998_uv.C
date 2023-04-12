TCutG *myProtonForwCut_1998_uv(){ 
   // cout<<"Il taglio 1998_uv è stato caricato"<<endl;

   TCutG *cutg = new TCutG("CUTG",36);
   cutg->SetVarX("Tof_trf[0]");
   cutg->SetVarY("De_trf[0]");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,11.4508,109.726);
   cutg->SetPoint(1,11.3651,180.763);
   cutg->SetPoint(2,14.3938,255.237);
   cutg->SetPoint(3,18.5368,373.249);
   cutg->SetPoint(4,21.0369,460.326);
   cutg->SetPoint(5,23.7656,576.047);
   cutg->SetPoint(6,26.4942,769.678);
   cutg->SetPoint(7,27.7657,949.561);
   cutg->SetPoint(8,28.3943,1065.28);
   cutg->SetPoint(9,29.2229,1065.28);
   cutg->SetPoint(10,31.0373,917.48);
   cutg->SetPoint(11,33.6231,734.16);
   cutg->SetPoint(12,36.9375,568.026);
   cutg->SetPoint(13,41.4234,383.561);
   cutg->SetPoint(14,45.7664,263.257);
   cutg->SetPoint(15,49.6666,186.492);
   cutg->SetPoint(16,55.9097,99.4147);
   cutg->SetPoint(17,56.9811,73.0624);
   cutg->SetPoint(18,54.3525,76.4997);
   cutg->SetPoint(19,49.7808,110.872);
   cutg->SetPoint(20,44.4949,231.176);
   cutg->SetPoint(21,39.7662,375.54);
   cutg->SetPoint(22,36.4946,494.698);
   cutg->SetPoint(23,33.5659,618.439);
   cutg->SetPoint(24,31.223,773.116);
   cutg->SetPoint(25,29.3801,901.44);
   cutg->SetPoint(26,28.7372,836.132);
   cutg->SetPoint(27,27.5657,707.808);
   cutg->SetPoint(28,25.3799,555.423);
   cutg->SetPoint(29,22.937,436.265);
   cutg->SetPoint(30,20.294,328.565);
   cutg->SetPoint(31,18.3939,275.86);
   cutg->SetPoint(32,16.051,200.241);
   cutg->SetPoint(33,13.7652,152.119);
   cutg->SetPoint(34,12.008,118.892);
   cutg->SetPoint(35,11.4508,109.726);

   return cutg;
}
