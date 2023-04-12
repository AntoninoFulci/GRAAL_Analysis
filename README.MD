Utilizzo:
-per utilizzare gli scripts bisogna:
  0) mettere la cartella con i codici "accanto" alle cartelle con i dati
  1) rinominare le cartelle da analizzare con un prefisso "data_"
  2) caricare la macro su root con ".L Analysis.C"
  3) istanziare la classe "Analysis o"
  4) utilizzare la funzione ProcessAll ("o.ProcessAll()")

########################################################################################
Codice Analisi GRAAL v1.06
- sistemazione tagli dei protoni in avanti.
- aggiunta del taglio degli eventi di tipo deuterio da un fit sugli eventi Tof vs dE_dx. IL taglio è differenziato in base al nome della cartella di lavoro.
########################################################################################
Codice Analisi GRAAL v1.05
Changelog:
- adesso il codice sceglie il giusto taglio in base alla cartella scelta
- non funziona più la compilazione del Loader.C

################################################################################
Codice Analisi GRAAL v1.04
Changelog:
- adesso dopo aver analizzato una cartella crea un file con <nome_cartella>_analizzato.root
- tolta la funzione per analizzare i file uno per uno
- aggiunti vari commenti per capire meglio il codice

################################################################################
Codice Analisi GRAAL v1.03
Changelog:
- aggiunti vari commenti alle funzioni
- spostata la funzione GetNames(---) in util.h
- pulizie nel codice

###############################################################################
Codice Analisi GRAAL v1.02
Changelog:
- fatto diventare l'agoritmo di processing una funzione che si prende un TTRee; questa lo inizializza e poi procede ad analizzare il file; in questo modo si può fare l'analisi dei file uno per uno senza avviare il programma manualmente più volte
- create due funzioni principali all'interno di Analysis.C, una per analizzare più file contemporaneamente e una per analizzarli tutti uno per uno
- creato file util.h al cui interno ci sono diverse funzioni che vengono utilizzate più volte
- creato file process.h che contiene l'algoritmo di processing
- create funzioni Setter e Clean che servono per settare l'ambiente di lavoro (per togliere i vari warning e per compilare il Loader.C)

################################################################################
Codice Analisi GRAAL v1.00
Changelog:
- spostato i cut in un header file, adesso sono delle funzioni che semplicemente ritornatno il Cut, in questo modo il codice è più pulito
- sistemato le indentazioni
- sostituito gli if consecutivi con else if in modo da rendere più veloce il programma
- risolto il problema delle librerie (almeno sul mio pc ) tramite uno script Loader.C che viene compilato all'interno di Analysis.C tramite   gROOT->ProcessLine(".L Loader.C+");
- aggiunto un clock in modo da calcolare quanto tempo impiega per analizzare uno o più files
- aggiunta funzione per ottenre un vector di stringe contente i nomi della cartella passata (path assoluto o relativo)
- aggiunta funzionalità di "contenare" tutti i file presenti
