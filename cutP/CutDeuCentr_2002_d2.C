TF1 *myCentrDeuCut_2002_d2(){
  TF1 *f_2002_d2 = new TF1("f_2002_d2","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.06,0.92);
  f_2002_d2->SetParameters(-95.090,168.53,-93.79,19.57);

  return f_2002_d2;
}
