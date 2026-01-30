TF1 *myCentrDeuCut_2005_d2(){
  TF1 *f_2005_d2 = new TF1("f_2005_d2","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.01,1.77);
  f_2005_d2->SetParameters(-106.88,176.22,-92.88,19.15);

  return f_2005_d2;
}
