///////////////////////////////////////////////////
// File utility contente diverse funzioni che
// vengono utilizzate durante il processing
// dei dati
///////////////////////////////////////////////////

//Funzione che ritorna un vettore di stringhe contente i nomi di tutti i file
//e carte presenti nel path passato
std::vector<std::string> Analysis::GetNames(string dir_name, bool debug = 0){
  DIR *dir;
  struct dirent *ent;
  vector<string> files;
  if ((dir = opendir (dir_name.c_str())) != NULL) {
    /* print all the files and directories within directory */
    while ((ent = readdir (dir)) != NULL) {
      if(debug) cout<<ent->d_name<<endl;
      files.push_back(ent->d_name);
    }
    closedir (dir);
  }
  return files;
}

//Funzione che ritorna un TTree con più file run....root
vector<TTree*> Analysis::InitializeAll(){

  //qui creo un vettore di stringe chiamato "directories" dalla funzione GetNames
  vector<string> directories = Analysis::GetNames("..");
  cout<<"Le cartelle che analizzerò sono: "<<endl;

  //questo for serve solo a stampare a schermo tutte le cartelle
  for(int i = 0; i < directories.size(); i++){
    if(directories[i].find("data_") != std::string::npos){
      // cout<<"["<<i<<"] "
      cout<<directories[i].substr(5,directories[i].size())<<endl;
    }
  }
  cout<<"------------"<<endl;

  //Inizio del codice che aggancia tutte i file .root
  vector<TTree*> alberi;

  for(auto dir_name : directories){
    TChain *chain = new TChain("h70","");
    if(dir_name.find("data_")!=std::string::npos){ //cerca solo le cartelle che iniziano con data
      string inside_dir = "../" + dir_name + "/";   //ricostruiamo il path
      vector<string> files = GetNames(inside_dir);   //otteniamo i nomi dei file dentro la cartella
      //ciclo che cerca i file .root dentro la cartella "inside_dir"
      for(auto file_name:files){
        //if(file_name.find("run")!= std::string::npos && file_name.find(".root")!=std::string::npos && file_name.find(".gz")==std::string::npos && file_name.find("_analizzato") == std::string::npos && file_name.find(".rootc")==std::string::npos){ //condizioni per ottenere solo i file voluti
        if(file_name.find("run")!=std::string::npos && file_name.find(".root")!=std::string::npos){
          if(file_name.find(".gz") != std::string::npos){ //caso in cui trova dei file compressi
            cout<<"Non sto analizzando il file: "<<file_name<<"controllare di averlo estratto!!!"<<endl;
          }
          else{
             // ricostruiamo il path del run
             string file_path = inside_dir + file_name;
             chain->Add(file_path.c_str());
          }
        }
      }
      //convertiamo la chain in un TTree
      TTree *tree;
      tree = chain;
      string titolo = dir_name.substr(5,dir_name.size());
      tree->SetTitle(titolo.c_str());
      //string nome_file = "../" + titolo + "_analizzato.root";
      alberi.push_back(tree);
    }
  }
  return alberi;
 }

//Funzione che ritorna un vettore di pair contenente il percorso del file run.root e il suo nome senza percorso
std::vector<std::pair<std::string, std::string>> Analysis::AllNames(){
  vector<string> directories = Analysis::GetNames("..");
  vector<pair<string,string>> paths_names;
  pair<string, string> coppia;

  for(auto dir_names : directories){
    if(dir_names.find("data_") != std::string::npos){
      // cout<<dir_names<<endl;
      string inside_dir = "../" + dir_names + "/";
      vector<string> files = GetNames(inside_dir);
      for(auto file_names : files){
        if(file_names.find("run") != std::string::npos && file_names.find(".root") != std::string::npos && file_names.find(".gz") == std::string::npos && file_names.find("_analizzato") == std::string::npos){
          // cout<<file_names<<endl;
          string file_path = inside_dir + file_names;
          coppia.first = file_path;
          coppia.second = file_names;
          paths_names.push_back(coppia);
        }
        else if(file_names.find(".gz") != std::string::npos){
          cout<<"Non sto analizzando il file: "<<file_names<<" controllare di averlo estratto!!!"<<endl;
        }
      }
    }
  }

  return paths_names;
}

//Funzione che serve per creare cartelle, passato il path
void Analysis::CreateFolder(string f_path, bool debug = 0){
  struct stat st;
	string path = f_path;
	if(stat(path.c_str(),&st) == 0){
  	if(debug) cout<<"The directory "<<path<<" already exists skipping creating it"<<endl;
	}
	else{
		cout<<path<<" does not exits, creating it"<<endl;
		mkdir(path.c_str(), ACCESSPERMS);
	}
}

//Funzione che setta l'enviroment
void Analysis::Setter(){

  cout<<"Setto l'enviroment per analizzare i dati..."<<endl;
  gErrorIgnoreLevel = 6001;
  gSystem->RedirectOutput("/dev/null");
  gROOT->ProcessLine(".L Loader.C+");
  gSystem->RedirectOutput(0,0);

}

//Funzione per ripulire la cartella dai file creati durante l'analisi
void Analysis::Clean(){
    remove("./Loader_C_ACLiC_dict_rdict.pcm");
    remove("./Loader_C.d");
    remove("./Loader_C.so");
}
