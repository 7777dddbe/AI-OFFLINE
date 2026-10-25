#PUNTO 1 - Importo in una lista il contenuto del file
f = open("dati.csv", "r") #apro il file in sola lettura (il file deve stare nella stessa cartella del programma)
ContenutoFile = [] #creo la lista per contenere le righe del file
for line in f: #scorro il file riga per riga
    if not line.startswith("City"): #escludo la prima riga (intestazione)
        ContenutoFile.append(line.strip()) #tolgo lo \n finale e aggiungo la riga alla lista
f.close() #chiudo il file
print("Edizioni lette dal file:", len(ContenutoFile))

#PUNTO 2 - Cerco se a Barcelona si sono svolte le olimpiadi invernali
trovata = False
for e in ContenutoFile:
    riga = e.split(";") #suddivido la riga in base al ;
    if riga[0] == "Barcelona" and riga[4] == "Winter": #colonna 0 = città, colonna 4 = stagione
        trovata = True

if trovata:
    print("A Barcelona si sono svolte le olimpiadi invernali")
else:
    print("A Barcelona NON si sono svolte le olimpiadi invernali")

#PUNTO 3 - Conto attraverso un dictionary il numero di edizioni per ogni città
ConteggioXCittà = {}
for e in ContenutoFile:
    riga = e.split(";")
    città = riga[0] #la città è nella prima colonna
    if città not in ConteggioXCittà:
        ConteggioXCittà[città] = 1 #se la città non è ancora nel dictionary la inserisco con valore 1
    else:
        ConteggioXCittà[città] += 1 #altrimenti incremento il conteggio
print("Edizioni per ogni città:", ConteggioXCittà)

#PUNTO 4 - Mostro gli anni delle olimpiadi della città con più edizioni
massimo = 0
cittàMax = ""
for città, valore in ConteggioXCittà.items(): #scorro le coppie città - numero di edizioni
    if valore > massimo:
        massimo = valore
        cittàMax = città

print("La città con più edizioni è", cittàMax, "con", massimo, "edizioni, negli anni:")
for e in ContenutoFile:
    riga = e.split(";")
    if riga[0] == cittàMax:
        print("-", riga[3], riga[4]) #colonna 3 = anno, colonna 4 = stagione

#PUNTO 5 - Verifico se si sono svolte più edizioni invernali che estive
invernali = 0
estive = 0
for e in ContenutoFile:
    riga = e.split(";")
    if riga[4] == "Winter":
        invernali += 1
    else:
        estive += 1

print("Edizioni invernali:", invernali, "- Edizioni estive:", estive)
if invernali > estive:
    print("Si sono svolte più edizioni invernali che estive")
elif invernali == estive:
    print("Le edizioni invernali e quelle estive sono lo stesso numero")
else:
    print("Si sono svolte più edizioni estive che invernali")

#PUNTO 6 - Inserisco in una lista le nazioni in cui si sono svolte le olimpiadi (senza duplicati)
nazioni = []
for e in ContenutoFile:
    riga = e.split(";")
    nazione = riga[1] #colonna 1 = codice della nazione
    if nazione not in nazioni: #la aggiungo solo se non c'è già
        nazioni.append(nazione)
print("Nazioni che hanno ospitato le olimpiadi:", nazioni)

#PUNTO 7 - Verifico se c'è un gap maggiore di 4 anni tra un'edizione e l'altra
#lo controllo separatamente per le olimpiadi estive e per quelle invernali
for stagione in ["Summer", "Winter"]:
    if stagione == "Summer":
        nome = "estive"
    else:
        nome = "invernali"

    anni = [] #lista con gli anni delle edizioni di questa stagione
    for e in ContenutoFile:
        riga = e.split(";")
        anno = int(riga[3]) #converto l'anno in numero per poter fare i calcoli
        if riga[4] == stagione and anno not in anni:
            anni.append(anno)
    anni.sort() #metto gli anni in ordine crescente

    gapTrovato = False
    for i in range(1, len(anni)): #parto da 1 perché confronto ogni anno con quello prima
        differenza = anni[i] - anni[i-1]
        if differenza > 4:
            gapTrovato = True
            print("Olimpiadi " + nome + ": gap di", differenza, "anni tra il", anni[i-1], "e il", anni[i])
            annoMancante = anni[i-1] + 4 #l'edizione si sarebbe dovuta svolgere 4 anni dopo la precedente
            while annoMancante < anni[i]: #possono mancare anche più edizioni di fila
                print("   si sarebbero dovute svolgere nel", annoMancante)
                annoMancante += 4
    if not gapTrovato:
        print("Olimpiadi " + nome + ": nessun gap maggiore di 4 anni")
