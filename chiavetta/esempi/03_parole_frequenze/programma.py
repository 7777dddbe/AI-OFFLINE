#PUNTO 1 [Facile] - Chiedo frasi o parole finché l'utente scrive STOP
lista = []
continua = True
while continua:
    frase = input("Inserisci una frase o una parola (STOP per finire): ")
    frase = frase.strip().lower() #tolgo gli spazi ai lati e converto in minuscolo
    if frase == "stop":
        continua = False #l'utente ha scritto STOP: esco dal ciclo
    elif frase != "": #non salvo le righe vuote
        lista.append(frase)
print("Parole inserite:", lista)

#PUNTO 2 [Intermedio] - Dictionary: lettera iniziale -> quante parole iniziano con quella lettera
conteggio = {}
for parola in lista:
    iniziale = parola[0] #prima lettera della parola
    if iniziale in conteggio:
        conteggio[iniziale] += 1 #incremento di uno il conteggio per quella lettera iniziale
    else:
        conteggio[iniziale] = 1 #creo un nuovo elemento con chiave la lettera iniziale e valore 1
print("Conteggio per lettera iniziale:", conteggio)

#PUNTO 3 [Intermedio - Ricerca] - L'utente cerca una lettera iniziale
lettera = input("Quale lettera iniziale vuoi cercare? ").strip().lower()
if lettera in conteggio:
    print("Ci sono", conteggio[lettera], "parole che iniziano con:", lettera)
    paroleDette = [] #serve a salvare le parole già mostrate per non ripeterle
    for parola in lista:
        if parola[0] == lettera and parola not in paroleDette:
            print("-", parola)
            paroleDette.append(parola)
else:
    print("Non ci sono parole che iniziano con:", lettera)

#PUNTO 4 [Avanzato] - Stringa con la prima e l'ultima lettera di ogni parola
stringa = ""
for i in range(len(lista)):
    if i % 2 == 0: #posizione pari -> MAIUSCOLO
        parola = lista[i].upper()
    else: #posizione dispari -> minuscolo
        parola = lista[i].lower()
    stringa += parola[0] + parola[-1] #aggiungo la prima e l'ultima lettera
print("Nuova stringa:", stringa)
