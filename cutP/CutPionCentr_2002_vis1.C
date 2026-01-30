TCutG *myPionCentrCut_2002_vis1(){
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06
   
   TCutG *cutg = new TCutG("CUTCentrPion_2002_vis1",22);
   cutg->SetVarX("Eclusc_track");
   cutg->SetVarY("Dedx_track");
   cutg->SetTitle("Graph");
   cutg->SetFillStyle(1000);
   cutg->SetPoint(0,0.305587,1.40625);
   cutg->SetPoint(1,0.327077,1.66667);
   cutg->SetPoint(2,0.327077,2.40451);
   cutg->SetPoint(3,0.305587,2.79514);
   cutg->SetPoint(4,0.25616,2.79514);
   cutg->SetPoint(5,0.183095,3.18576);
   cutg->SetPoint(6,0.140115,3.35937);
   cutg->SetPoint(7,0.0799427,4.22743);
   cutg->SetPoint(8,0.0606017,5.00868);
   cutg->SetPoint(9,0.0412607,5.92014);
   cutg->SetPoint(10,0.0240688,6.9184);
   cutg->SetPoint(11,0.00902578,6.39757);
   cutg->SetPoint(12,0.0154728,5.00868);
   cutg->SetPoint(13,0.00902578,3.35937);
   cutg->SetPoint(14,0.00902578,1.79687);
   cutg->SetPoint(15,0.00902578,0.972222);
   cutg->SetPoint(16,0.0563037,1.97049);
   cutg->SetPoint(17,0.0971347,1.53646);
   cutg->SetPoint(18,0.19384,1.23264);
   cutg->SetPoint(19,0.292693,1.36285);
   cutg->SetPoint(20,0.307736,1.31944);
   cutg->SetPoint(21,0.305587,1.40625);
   
   return cutg;
}
