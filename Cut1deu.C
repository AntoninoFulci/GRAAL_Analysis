bool Cut1deu(vector<TLorentzVector> proton, vector<TLorentzVector> fneutron, vector<TLorentzVector> fDeuteron){
  bool val=0;
  if(proton.size()==0 && fneutron.size()==0 && fDeuteron.size()==1){
    val=1;
  }
  return val;
}
