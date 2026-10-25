fastaFileA = open('./alleleA.fa')
seqList19A = []
seqList20A = []
sequenza19A = ""
sequenza20A = ""
chr = 0
for line in fastaFileA:
    if line.startswith(">"):
        if "chr19" in line:
            chr = 19
        else: 
            chr = 20
    else:
        if chr == 19:
            #aggiunge alla lista la riga letta dal file, togliendo gli spazi eventuali
            seqList19A.append(line.strip())
        else:
            seqList20A.append(line.strip())
    
#chiude il file   
fastaFileA.close()
sequenza19A = "".join(seqList19A)
sequenza20A = "".join(seqList20A)

print(len(sequenza19A))

variants = open('./variants.vcf')
positions = []
refs = []
alts = []
outcomes = []

for line in variants:
    if not line.startswith("#"):
        riga = line.split("\t")
        positions.append(int(riga[1]))
        refs.append(riga[3])
        alts.append(riga[4])
        

print (alts)

