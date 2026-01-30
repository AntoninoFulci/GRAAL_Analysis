TCutG *myPionCentrCut_1999_vis(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_1999_vis",21);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0154728,1.05903);
   cutg->SetPoint(1,0.0369627,1.53646);
   cutg->SetPoint(2,0.0520057,2.53472);
   cutg->SetPoint(3,0.0734957,2.1441);
   cutg->SetPoint(4,0.142264,1.66667);
   cutg->SetPoint(5,0.23467,1.53646);
   cutg->SetPoint(6,0.29914,1.44965);
   cutg->SetPoint(7,0.32063,2.2309);
   cutg->SetPoint(8,0.281948,2.75174);
   cutg->SetPoint(9,0.238968,3.01215);
   cutg->SetPoint(10,0.191691,3.01215);
   cutg->SetPoint(11,0.146562,3.22917);
   cutg->SetPoint(12,0.112178,3.61979);
   cutg->SetPoint(13,0.0799427,4.40104);
   cutg->SetPoint(14,0.0412607,5.57292);
   cutg->SetPoint(15,0.0219198,6.9184);
   cutg->SetPoint(16,0.0154728,5.52951);
   cutg->SetPoint(17,0.0154728,3.27257);
   cutg->SetPoint(18,0.0176218,2.40451);
   cutg->SetPoint(19,0.0176218,0.928819);
   cutg->SetPoint(20,0.0154728,1.05903);
   
   return cutg;
}
