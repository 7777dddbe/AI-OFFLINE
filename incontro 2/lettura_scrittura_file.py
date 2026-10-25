#ESEMPIO DI LETTURA DA FILE DELLE RIGHE DI BASI E IMPORTAZIONE IN UN'UNICA STRINGA
fastaFileA = open('./alleleA.fa')
seqList = []
sequenzaA = ""

for line in fastaFileA:
    #aggiunge alla lista la riga letta dal file, togliendo gli spazi eventuali
    seqList.append(line.strip())
#chiude il file   
fastaFileA.close()

#concatena gli elementi della lista nella stringa per poter avere tutte le basi con un indice unico
#questo metodo è molto più efficiente che aggiungere direttamente le righe alla stringa
sequenza19A = "".join(seq19List)

#ESEMPIO DI SCRITTURA SU FILE
#Apro il file dal quale prendere le righe da modificare
varianti = open('./variants.vcf')

# apriamo un file nuovo che non esiste, usiamo l'argomento w per indicare che ci vogliamo scrivere. ATTENZIONE, se usate un file che esiste già questo si sovrascrive e perdete i dati di quel file
variantiNuovo = open('./variantsNuovo.vcf','w')
#con il seguente codice creeremo una copia del file variants aggiungendo una colonna iniziale contentente un codice progressivo
i=0
for line in varianti: #per ogni riga del file aperto
    i+=1
    variantiNuovo.write(i + "\t" + line.strip()) #aggiunge una colonna con il numero di linea e scrive la riga nel nuovo file
#chiude entrambi i file
varianti.close()
variantiNuovo.close()