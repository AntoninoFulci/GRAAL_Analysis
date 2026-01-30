TF1 *myCentrDeuCut_2002_d1(){
  TF1 *f_2002_d1 = new TF1("f_2002_d1","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.04,0.86);
  f_2002_d1->SetParameters(-102.8,165.69,-85.52,18.54);

   return f_2002_d1;  
}
