TCutG* PionCntCut_1998_uv(){
//========= Macro generated from object: PionCentrCut/
//========= by ROOT version6.28/06
    TCutG *cutg = new TCutG("PionCntCut_1998_uv",19);
    cutg->SetVarX("Eclusc_track");
    cutg->SetVarY("Dedx_track");
    cutg->SetTitle("Graph");
    cutg->SetFillStyle(1000);
    cutg->SetPoint(0,0.0536919,2.58681);
    cutg->SetPoint(1,0.0404673,3.06424);
    cutg->SetPoint(2,0.0378224,4.36632);
    cutg->SetPoint(3,0.0404673,4.84375);
    cutg->SetPoint(4,0.0431122,4.80035);
    cutg->SetPoint(5,0.0616266,4.0625);
    cutg->SetPoint(6,0.0801411,3.71528);
    cutg->SetPoint(7,0.1013,3.36806);
    cutg->SetPoint(8,0.188583,2.97743);
    cutg->SetPoint(9,0.217677,3.10764);
    cutg->SetPoint(10,0.262641,2.84722);
    cutg->SetPoint(11,0.336698,2.5);
    cutg->SetPoint(12,0.352568,2.02257);
    cutg->SetPoint(13,0.344633,1.67535);
    cutg->SetPoint(14,0.28909,1.45833);
    cutg->SetPoint(15,0.172713,1.76215);
    cutg->SetPoint(16,0.0774961,2.19618);
    cutg->SetPoint(17,0.0563368,2.58681);
    cutg->SetPoint(18,0.0536919,2.58681);

    return cutg;
}
