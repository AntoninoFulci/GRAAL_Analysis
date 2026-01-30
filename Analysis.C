#define Analysis_cxx
#include "Analysis.h"
#include <TH2.h>
#include <TStyle.h>
#include <TCanvas.h>
#include <vector>
#include <stdio.h>
#include "TLorentzVector.h"
#include "TFile.h"
#include "TTree.h"
#include "TSystem.h"
#include "TCutG.h"
#include "cut.h"
#include <chrono>
#include "util.h"
#include "process.h"


//Utilizzando questa funzione si avvia l'analisi di tutti i files
//o di tutti i file in una cartella
void Analysis::ProcessAll(){

  //metodo che setta i file per poter scrivere nel root file i vettori di TLorentzVector
  Setter();

  //prendiamo il tempo prima dell'inizio dell'analisi dei dati
  auto start = std::chrono::steady_clock::now();

  //la funzione InitializeAll permette di creare un vettore di TTree, dove ogni elemento è un albero formato
  //da una chain di tutti i file root di una cartella (cartella->tutti i file root->chain->TTree->nel vettore)
  vector<TTree*> alberi = InitializeAll();

  //per ogni TTree nel vettore (quindi per ogni cartella) processiamo i dati
  for(auto albero : alberi){
    //convertiamo il titolo dell'albero in stringa (perchè di default root usa array di caratteri)
    string titolo(albero->GetTitle());

    //formiamo il path del file in uscita
    string nome_file = "../" + titolo + "_analizzato.root";

    cout<<"Sto analizzando la cartella "<<titolo<<"..."<<endl;

    //avviamo l'analisi
    process(albero, nome_file.c_str(), titolo);
  }

  //stampiamo il tempo trascorso da quando ha iniziato a finire di analizzare i file
  cout<<"("<<since(start).count()<<"s)"<<endl;

  //funzione che serve a cancellare i file creati dal setter (utile se il codice gira su diverse macchine)
  Clean();

}
