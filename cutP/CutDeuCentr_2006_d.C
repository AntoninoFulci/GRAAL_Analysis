TF1 *myCentrDeuCut_2006_d(){
  TF1 *f_2006_d = new TF1("f_2006_d","[0]*pow(x,5)+[1]*pow(x,4)+[2]*pow(x,3)+[3]*pow(x,2)+[4]*x+[5]",0.,0.8);
  f_2006_d->SetParameters(-372.71,1034.69,-1114.18,575.45,-148.26,20.31);

  return f_2006_d;
}
