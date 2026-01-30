TF1 *myCentrDeuCut_2005_d1(){
  TF1 *f_2005_d1 = new TF1("f_2005_d1","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.01,1.77);
  f_2005_d1->SetParameters(-370.49,396.65,-138.60,21.13);

  return f_2005_d1;
}  
