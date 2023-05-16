TF1 *ForwDeuFit_2002_d1(void){

  TF1 *f = new TF1("f","[0]*pow(x,2)+[1]*x+[2]",30.66,55.20);
  f->SetParameters(0.085, -9.464, 275.117);

  return f;
}


TF1 *ForwDeuFit_2002_d3(void){

  TF1 *f = new TF1("f","[0]*pow(x,2)+[1]*x+[2]",29.99,57.96);
  f->SetParameters(0.074,-8.82,271.35);

  return f;
}

TF1 *ForwDeuFit_2005_d2(void){

  TF1 *f = new TF1("f","[0]*pow(x,2)+[1]*x+[2]",33.18,70);
  f->SetParameters(0.074,-8.82,271.35);

  return f;
}

TF1 *ForwDeuFit_2006_d(void){

  TF1 *f = new TF1("f","[0]*pow(x,2)+[1]*x+[2]",33.18,57.89);
  f->SetParameters(0.052,-6.55,208.75);

  return f;
}

