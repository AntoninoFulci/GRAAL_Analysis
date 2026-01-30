TF1 *myCentrDeuCut_1999_d1(){
  TF1 *f_1999_d1 = new TF1("f_1999_d1","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.03,0.68);
  f_1999_d1->SetParameters(-184.90,246.20,-107.40,19.54);

  return f_1999_d1;
  
}
