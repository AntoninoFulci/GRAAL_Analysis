bool Cut1fch_4ph(vector<TLorentzVector> fneutron, vector<pair<double,double>> pionangles, vector<pair<double,double>> fphotonangles, vector<TLorentzVector> cphoton, int fch){
bool val=0;
 if(fch==1 && cphoton.size()==4 && fneutron.size()==0 && pionangles.size()==0 && fphotonangles.size()==0){
    val=1;
 }
 return val;
}
