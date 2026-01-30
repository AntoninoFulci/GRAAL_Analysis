TF1 *myCentrDeuCut_2002_d3(){
  TF1 *f_2002_d3 = new TF1("f_2002_d3","[0]*pow(x,5)+[1]*pow(x,4)+[2]*pow(x,3)+[3]*pow(x,2)+[4]*x+[5]",0.,0.8);
  f_2002_d3->SetParameters(-570.89,1567.5,-1613.94,774.68,-181.4,22.3);

  return f_2002_d3;
}  
