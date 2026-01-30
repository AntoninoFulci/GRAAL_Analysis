TCutG* myProtonCentrCut_2005_d1(){
//========= Macro generated from object: myProtonCentrCut/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPro_2005_d1",20);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.146562,4.01042);
   cutg->SetPoint(1,0.0842407,5.96354);
   cutg->SetPoint(2,0.0477077,7.69965);
   cutg->SetPoint(3,0.0283668,10.1302);
   cutg->SetPoint(4,0.00902578,12.5174);
   cutg->SetPoint(5,0.0111748,14.2969);
   cutg->SetPoint(6,0.0111748,16.0764);
   cutg->SetPoint(7,0.0176218,18.2899);
   cutg->SetPoint(8,0.0412607,17.8993);
   cutg->SetPoint(9,0.0455587,14.3403);
   cutg->SetPoint(10,0.0627507,11.0851);
   cutg->SetPoint(11,0.103582,8.17708);
   cutg->SetPoint(12,0.189542,6.13715);
   cutg->SetPoint(13,0.327077,4.61806);
   cutg->SetPoint(14,0.380802,3.75);
   cutg->SetPoint(15,0.27765,3.09896);
   cutg->SetPoint(16,0.219628,3.35937);
   cutg->SetPoint(17,0.170201,3.7066);
   cutg->SetPoint(18,0.15086,3.96701);
   cutg->SetPoint(19,0.146562,4.01042);
   
   
   return cutg;
}
