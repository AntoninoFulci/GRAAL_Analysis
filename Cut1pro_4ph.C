bool Cut1pro_4ph(vector<TLorentzVector> proton, vector<TLorentzVector> fneutron, vector<TLorentzVector> fDeuteron, vector<TLorentzVector> cphoton, vector<pair<double,double>> pionangles, vector<pair<double,double>> fphotonangles){
  bool val=0;
  if(proton.size()==1 && fneutron.size()==0 && fDeuteron.size()==0 && cphoton.size()==4 && fphotonangles.size()==0 && pionangles.size()==0){
    val=1;
  }
  return val;
}
