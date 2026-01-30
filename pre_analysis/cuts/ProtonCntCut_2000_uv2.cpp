TCutG* ProtonCntCut_2000_uv2(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("ProtonCntCut_2000_uv2",26);
   cutg->SetVarX("Ecusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0391117,8.13368);
   cutg->SetPoint(1,0.0197708,9.13194);
   cutg->SetPoint(2,0.0133238,10.9115);
   cutg->SetPoint(3,0.0111748,12.6042);
   cutg->SetPoint(4,0.0154728,15.1649);
   cutg->SetPoint(5,0.00902578,16.5104);
   cutg->SetPoint(6,0.0154728,18.2031);
   cutg->SetPoint(7,0.0176218,19.9826);
   cutg->SetPoint(8,0.0455587,20.026);
   cutg->SetPoint(9,0.0455587,16.5972);
   cutg->SetPoint(10,0.0541547,14.1233);
   cutg->SetPoint(11,0.0777937,11.5191);
   cutg->SetPoint(12,0.0928367,9.43576);
   cutg->SetPoint(13,0.135817,7.87326);
   cutg->SetPoint(14,0.198138,6.26736);
   cutg->SetPoint(15,0.284097,5.18229);
   cutg->SetPoint(16,0.365759,4.09722);
   cutg->SetPoint(17,0.42808,3.44618);
   cutg->SetPoint(18,0.434527,3.18576);
   cutg->SetPoint(19,0.436676,2.62153);
   cutg->SetPoint(20,0.361461,2.70833);
   cutg->SetPoint(21,0.355014,2.70833);
   cutg->SetPoint(22,0.185244,3.88021);
   cutg->SetPoint(23,0.12937,4.66146);
   cutg->SetPoint(24,0.0756447,5.83333);
   cutg->SetPoint(25,0.0391117,8.13368);
   
   return cutg;
}
