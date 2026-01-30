TF1 *myCentrDeuCut_1999_d2(){
  TF1 *f_1999_d2 = new TF1("f_1999_d2","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.04,1.18);
  f_1999_d2->SetParameters(-38.39,87.86,-63.33,17.07);

  return f_1999_d2;
}
