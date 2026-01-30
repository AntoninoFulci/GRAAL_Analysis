TCutG *myPionCentrCut_2002_uv1(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2002_uv1",18);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.0171944,8.08926);
   cutg->SetPoint(1,0.0361938,6.28063);
   cutg->SetPoint(2,0.0665928,4.76371);
   cutg->SetPoint(3,0.0979417,3.85939);
   cutg->SetPoint(4,0.16159,3.1301);
   cutg->SetPoint(5,0.210038,2.83839);
   cutg->SetPoint(6,0.210038,2.83839);
   cutg->SetPoint(7,0.303438,2.70833);
   cutg->SetPoint(8,0.327077,2.2309);
   cutg->SetPoint(9,0.331375,1.79687);
   cutg->SetPoint(10,0.318481,1.49306);
   cutg->SetPoint(11,0.32063,1.36285);
   cutg->SetPoint(12,0.258309,1.36285);
   cutg->SetPoint(13,0.0842407,1.57986);
   cutg->SetPoint(14,0.0086447,1.02975);
   cutg->SetPoint(15,0.00959467,8.06009);
   cutg->SetPoint(16,0.0171944,8.08926);
   cutg->SetPoint(17,0.0171944,8.08926);
   
   return cutg;
}
