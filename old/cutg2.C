// taglio energia fascio vs angolo theta del neutrone sopra la soglia
{
//========= Macro generated from object: CUTG/Graph
//========= by ROOT version6.28/06

   TCutG *CutThetaNEg = new TCutG("CUTG",23);
   CutThetaNEg->SetVarX("energy gamma(GeV)");
   CutThetaNEg->SetVarY("theta neutrone(degree)");
   CutThetaNEg->SetTitle("Graph");
   CutThetaNEg->SetFillStyle(1000);
   CutThetaNEg->SetPoint(0,1.44722,0.49181);
   CutThetaNEg->SetPoint(1,1.44887,4.80703);
   CutThetaNEg->SetPoint(2,1.45561,6.94157);
   CutThetaNEg->SetPoint(3,1.45971,7.91181);
   CutThetaNEg->SetPoint(4,1.46425,8.92518);
   CutThetaNEg->SetPoint(5,1.46921,9.67982);
   CutThetaNEg->SetPoint(6,1.47705,10.8872);
   CutThetaNEg->SetPoint(7,1.48581,12.03);
   CutThetaNEg->SetPoint(8,1.49506,13.108);
   CutThetaNEg->SetPoint(9,1.5037,14.1429);
   CutThetaNEg->SetPoint(10,1.51295,15.0054);
   CutThetaNEg->SetPoint(11,1.56444,18.4994);
   CutThetaNEg->SetPoint(12,1.563,13.2991);
   CutThetaNEg->SetPoint(13,1.56071,10.9087);
   CutThetaNEg->SetPoint(14,1.56014,8.05698);
   CutThetaNEg->SetPoint(15,1.5587,3.73745);
   CutThetaNEg->SetPoint(16,1.55813,1.0954);
   CutThetaNEg->SetPoint(17,1.55842,0.424405);
   CutThetaNEg->SetPoint(18,1.52833,0.34053);
   CutThetaNEg->SetPoint(19,1.50684,0.34053);
   CutThetaNEg->SetPoint(20,1.49022,0.298593);
   CutThetaNEg->SetPoint(21,1.47991,0.214719);
   CutThetaNEg->SetPoint(22,1.44722,0.49181);
   CutThetaNEg->Draw("");
}
