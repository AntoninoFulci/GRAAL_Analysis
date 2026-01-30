TF1 *myCentrDeuCut_2001_d(){
   TF1 *f_2001_d = new TF1("f_2001_d","[0]*pow(x,3)+[1]*pow(x,2)+[2]*x+[3]",0.05,0.37);
   f_2001_d->SetParameters(-896.75,722.28,-198.63,24.42);

   return f_2001_d;   
}
