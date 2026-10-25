#PUNTO 1 - Carico le sequenze dei cromosomi 19 e 20 dai file alleleA.fa e alleleB.fa
#so che in ogni file fasta c'è prima il cromosoma 19 e poi il 20
sequenze = {} #chiave = allele + cromosoma (es. "A19"), valore = sequenza completa
for allele in ["A", "B"]:
    fastaFile = open("allele" + allele + ".fa", "r")
    righe19 = [] #righe di basi del cromosoma 19
    righe20 = [] #righe di basi del cromosoma 20
    cromosoma = 0
    for line in fastaFile: #scorro il file riga per riga
        if line.startswith(">"): #riga di intestazione: inizia un nuovo cromosoma
            if cromosoma == 0:
                cromosoma = 19
            else:
                cromosoma = 20
        elif cromosoma == 19:
            righe19.append(line.strip()) #aggiungo la riga togliendo lo \n e gli spazi
        elif cromosoma == 20:
            righe20.append(line.strip())
    fastaFile.close() #chiudo il file

    #unisco le righe in un'unica stringa (join è molto più veloce che sommare le stringhe)
    sequenze[allele + "19"] = "".join(righe19)
    sequenze[allele + "20"] = "".join(righe20)
    print("Lunghezza cromosoma 19" + allele + ": " + str(len(sequenze[allele + "19"])) + " basi")
    print("Lunghezza cromosoma 20" + allele + ": " + str(len(sequenze[allele + "20"])) + " basi")

#PUNTO 2 - Leggo il file delle varianti (colonne separate da \t)
cromosomi = [] #cromosoma di ogni variante
posizioni = [] #posizione della base da verificare
refs = [] #base di riferimento
varianti = open("variants.vcf", "r")
for line in varianti:
    if not line.startswith("#"): #salto le righe di annotazione
        campi = line.strip().split("\t")
        cromosomi.append(campi[0].replace("chr", "")) #tengo solo il numero (es. "19")
        posizioni.append(int(campi[1]))
        refs.append(campi[3].upper())
varianti.close()
print("Varianti lette dal file:", len(posizioni))

#PUNTO 3 - Salvo in una lista il valore del controllo per ogni variante
controlli = []
for i in range(len(posizioni)):
    #le posizioni del vcf partono da 1, gli indici di Python da 0: tolgo 1
    #uso upper() perché le sequenze possono avere lettere minuscole
    baseA = sequenze["A" + cromosomi[i]][posizioni[i] - 1].upper()
    baseB = sequenze["B" + cromosomi[i]][posizioni[i] - 1].upper()
    if baseA == refs[i] and baseB == refs[i]:
        controlli.append("0/0") #nessuna variazione
    elif baseA != refs[i] and baseB == refs[i]:
        controlli.append("1/0") #variazione solo nell'allele A
    elif baseA == refs[i] and baseB != refs[i]:
        controlli.append("0/1") #variazione solo nell'allele B
    else:
        controlli.append("1/1") #variazione in entrambi gli alleli

#PUNTO 4 - Conto il numero di variazioni (tutti i controlli diversi da 0/0)
numeroVariazioni = 0
for c in controlli:
    if c != "0/0":
        numeroVariazioni += 1
print("Numero di variazioni trovate:", numeroVariazioni)

#OPZIONALE - Creo una copia del file delle varianti con la colonna del controllo in fondo
varianti = open("variants.vcf", "r")
variantiNuovo = open("variantsNuovo.vcf", "w") #ATTENZIONE: con "w" se il file esiste viene sovrascritto
i = 0 #indice per sapere a quale controllo sono arrivato
for line in varianti:
    if line.startswith("##"):
        variantiNuovo.write(line) #le righe di annotazione le copio così come sono
    elif line.startswith("#"):
        variantiNuovo.write(line.strip() + "\tCONTROLLO\n") #aggiungo il nome della nuova colonna
    else:
        #tolgo lo \n, aggiungo \t e il controllo, poi rimetto lo \n per andare a capo
        variantiNuovo.write(line.strip() + "\t" + controlli[i] + "\n")
        i += 1
varianti.close()
variantiNuovo.close()
print("Creato il file variantsNuovo.vcf con la colonna del controllo")
