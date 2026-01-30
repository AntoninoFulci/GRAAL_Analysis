bool Cut1deu_2ph(vector<TLorentzVector> proton, vector<TLorentzVector> fneutron, vector<TLorentzVector> fDeuteron, vector<TLorentzVector> cphoton, vector<pair<double,double>> fphotonangles, vector<pair<double,double>> pionangles){
  bool val=0;
  if(proton.size()==0 && fneutron.size()==0 && fDeuteron.size()==1 && cphoton.size()==2 && fphotonangles.size()==0 && pionangles.size()==0){
    val=1;
  }
  return val;
}
