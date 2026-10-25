'''
Lo scopo di questa esercitazione è identificare le varianti di un individuo date le sequenze genetiche di due cromosomi e rappresentarle in un formato più comodo per altre analisi.
Ogni cromosoma è presente in due copie (che chiamaremo alleleA e alleleB) ognuno ereditato da uno dei due genitori biologici.
I files alleleA.fa e alleleB.fa che vi ho fornito contengono entrambi i cromosomi 19 e 20, ognuno dei file rappresenta una copia di quel cromosoma; 
allelleA rappresenta il cromosoma ereditato da uno dei genitori; alleleB rappresenta il cromosoma ereditato dall'altro genitore. Le sequenze saranno quindi leggermente diverse.

- Caricare le sequenze di entrambe le copie (A e B) dei due cromosomi

'''

fastaFileA = open('./alleleA.fa')
seq19List = []
seq20List = []
sequenza19A = ""
sequenza20A = ""

# so che i cromosomi nel mio file fasta sono ordinato (prima il cromosoma 19, poi il 20), uso l'indice i per capire ad ogni linea quale cromosoma sto leggendo.
# parto con i=0, appena trovo il simbolo > metto i a 19, tutte le linee successive le aggiungo alla stringa sequenza19A, poi dal secondo > aumento l'indice i e cambio stringa
i = 0
for line in fastaFileA:
    if line.startswith('>'):
        if i==0:
            i=19
        else:
            i+=1
    else:
        if i==19:
            seq19List.append(line.strip())
        elif i==20:
            seq20List.append(line.strip())
fastaFileA.close()
#concatena gli elementi della lista nella stringa
sequenza19A = "".join(seq19List)

# Stessa cosa per alleleB
fastaFileB = open('./alleleB.fa')
sequenza19B = ""
sequenza20B = ""

i = 0
for line in fastaFileB:
    if line.startswith('>'):
        if i==0:
            i=19
        else:
            i+=1
    else:
        if i==19:
            sequenza19B+=line.strip()
        elif i==20:
            sequenza20B+=line.strip()
fastaFileB.close()

# Controllo la lunghezza delle stringhe e verifico che la lunghezza della sequenza genica dei due cromosomi corrisponda a quella riportata nel file chrNameLength.txt che contiene
# per ogni cromosoma la lunghezza delle sequenza di riferimento. Solo per essere sicuro di aver caricato correttamente i files.

print("La lunghezza del cromosoma 19A è: " + str(len(sequenza19A)) + " basi")
print("La lunghezza del cromosoma 19B è: " + str(len(sequenza19B)) + " basi")
print("La lunghezza del cromosoma 20A è: " + str(len(sequenza20A)) + " basi")
print("La lunghezza del cromosoma 20B è: " + str(len(sequenza20B)) + " basi")


# Ora possiamo caricare il file con le posizioni di tutte le varianti per i cromosomi 19 e 20. Creeremo 3 liste per ogni cromosoma:
# una con la posizione della variante, una con le basi di riferimento e una con le basi alternative.
# Per ogni linea (che non inizia con #, perché sono linee di annotazione che non ci interessano) del file useremo .split("\t"), per ottenere una lista con gli elementi delle colonne

posizione19=[]
reference19=[]
alternative19=[]

posizione20=[]
reference20=[]
alternative20=[]

varianti = open('./variants.vcf')
for line in varianti:
    if not line.startswith('#'):
        splitted = line.strip().split("\t")
        if int(splitted[0])==19:
            posizione19.append(int(splitted[1]))
            reference19.append(splitted[3])
            alternative19.append(splitted[4])
        elif int(splitted[0])==20:
            posizione20.append(int(splitted[1]))
            reference20.append(splitted[3])
            alternative20.append(splitted[4])
varianti.close()

print("Il numero di varianti nel cromosoma 19 sono: " + str(len(posizione19)))
print("Il numero di varianti nel cromosoma 20 sono: " + str(len(posizione20)))

# Ora non ci resta che controllare ogni posizione di ogni cromosoma, cosa vediamo nelle sequenze dei due alleli?
# Avendo a disposizione entrambi gli alleli di questo individuo possiamo verificare in ogni posizione se le varianti sono omozigote (basi identiche in entrambe le copie) oppure eterozigote (basi diverse)
# Per convenzione se in una posizione è presente la base di riferimento questa viene rappresentata con uno 0, se invece è presente la base alternativa questa viene rappresentata con un 1
# Dato che ci sono 2 copie di ogni cromosoma dobbiamo rappresentare entrambe le basi per ogni posizione, e si rappresentano con il simbolo / in mezzo:
# 0/0 per rappresentare che la variante di questo individuo è omozigota per la base di riferimento, 0/1 oppure 1/0 (sono equivalenti) per rappresentare che la posizione
# è eterozigota (ci sarà la base di riferimento su un allele e la base alternativa sull'altro allele) e 1/1 per rappresentare che la variante è omozigota per la base alternativa

varianti19 = []
for i in range(len(posizione19)):
    # dato che la posizione delle varianti sono 1-based, devo togliere 1 per ottenere la stessa posizione nella sequenza (python è 0-based)
    # ricordate sempre di usare la funzione upper(). la sequenza può contenere sia caratteri minuscoli che maiuscoli (il file delle varianti no)
    baseA = sequenza19A[posizione19[i]-1].upper()
    baseB = sequenza19B[posizione19[i]-1].upper()
    if baseA==reference19[i]:
        baseAconv='0'
    elif baseA==alternative19[i]:
        baseAconv='1'
    else:
        baseAconv='.'
    if baseB==reference19[i]:
        baseBconv='0'
    elif baseB==alternative19[i]:
        baseBconv='1'
    else:
        baseBconv='.'
    varianti19.append(baseAconv + '/' + baseBconv)

varianti20 = []
for i in range(len(posizione20)):
    # dato che la posizione delle varianti sono 1-based, devo togliere 1 per ottenere la stessa posizione nella sequenza (python è 0-based)
    # ricordate sempre di usare la funzione upper(). la sequenza può contenere sia caratteri minuscoli che maiuscoli (il file delle varianti no). Quindi quando troviamo una base in minuscolo la rendiamo maiuscola per poterla confrontare
    baseA = sequenza20A[posizione20[i]-1].upper()
    baseB = sequenza20B[posizione20[i]-1].upper()
    if baseA==reference20[i]:
        baseAconv='0'
    elif baseA==alternative20[i]:
        baseAconv='1'
    else:
        baseAconv='.'
    if baseB==reference20[i]:
        baseBconv='0'
    elif baseB==alternative20[i]:
        baseBconv='1'
    else:
        baseBconv='.'
    varianti20.append(baseAconv + '/' + baseBconv)


# Ora avete due liste, una per il cromosoma 19 e una per il cromosoma 20, con tutte le varianti codificate per questo individuo
#####################
# EXTRA
# A questo punto potete anche salvare questa informazione nel file delle varianti, come nuova colonna per poterla avere quando vi tornerà più comodo e non conservare le sequenze genomiche
# è molto più facile lavorare su questo file che sull'intera sequenza

varianti = open('./variants.vcf')

# apriamo un file nuovo che non esiste, usiamo l'argomento w per indicare che ci vogliamo scrivere. ATTENZIONE, se usate un file che esiste già questo si sovrascrive e perdete i dati di quel file
variantiNuovo = open('./variantsNuovo.vcf','w')
varianti19_20 = varianti19 + varianti20

i=0
for line in varianti:
    # Se troviamo una linea del file che inizia con ## la riscriviamo nel nuovo file
    if line.startswith('##'):
        variantiNuovo.write(line)
    # Se troviamo la linea (è solo una) che inizia con # allora ci aggiungiamo il nome della colonna nuova (nome dell'individuo)
    # dobbiamo fare prima lo strip per togliere lo \n che trova in fondo, aggiungere quello che vogliamo e ricordarci di rimettere lo \n altrimenti la linea dopo NON sarà a capo
    elif line.startswith('#'):
        variantiNuovo.write(line.strip() + "\tHG00096\n")
    # Per tutte le altre linee aggiungiamo la codifica delle varianti che abbiamo ottenuto prima. Usimao l'indice i per tenere traccia del punto in cui siamo arrivati a scrivere
    else:
        variantiNuovo.write(line.strip() + "\t" + varianti19_20[i] + "\n")
        i += 1
varianti.close()
variantiNuovo.close()