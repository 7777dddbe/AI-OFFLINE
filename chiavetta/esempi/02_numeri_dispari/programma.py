from random import randint #importo la funzione per generare numeri casuali

#PUNTO 1 [Facile] - Genero una lista di 80 numeri casuali DISPARI tra 1 e 49
numeri = []
for i in range(80):
    #randint(0,24) dà un numero da 0 a 24: moltiplicato per 2 e +1 diventa un dispari da 1 a 49
    numeri.append(randint(0, 24) * 2 + 1)
print("Lista dei numeri:", numeri)

#PUNTO 2 [Intermedio] - Creo un dictionary con le posizioni in cui compare ogni numero
Indici = {} #chiave = numero, valore = lista delle posizioni
for i in range(len(numeri)): #scorro la lista usando l'indice
    n = numeri[i]
    if n in Indici:
        Indici[n].append(i) #il numero c'è già: aggiungo la posizione alla sua lista
    else:
        Indici[n] = [i] #il numero non c'è ancora: creo la lista con la prima posizione
print("Posizioni di ogni numero:", Indici)

#PUNTO 3 [Avanzato] - Uso SOLO il dictionary (senza ri-scorrere la lista numeri)
#cerco quante volte compare il numero più frequente
massimo = 0
for n, posizioni in Indici.items():
    if len(posizioni) > massimo: #la lunghezza della lista = quante volte compare il numero
        massimo = len(posizioni)

#metto in una lista tutti i numeri che compaiono "massimo" volte (possono essere più di uno)
piùFrequenti = []
for n, posizioni in Indici.items():
    if len(posizioni) == massimo:
        piùFrequenti.append(n)
print("Numero/i più frequente/i:", piùFrequenti, "- compare/compaiono", massimo, "volte")

#per ognuno calcolo la distanza tra la prima e l'ultima volta che compare
distanzaMax = 0
for n in piùFrequenti:
    posizioni = Indici[n]
    distanza = posizioni[-1] - posizioni[0] #ultima posizione meno prima posizione
    print("Il numero", n, "compare la prima volta in posizione", posizioni[0], "e l'ultima in posizione", posizioni[-1], "- distanza:", distanza)
    if distanza > distanzaMax:
        distanzaMax = distanza
print("La distanza massima è:", distanzaMax)
