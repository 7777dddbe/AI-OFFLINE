"""AI Python Offline: scrivi l'esercizio, l'AI (sulla chiavetta, senza internet) scrive il programma.

Avvio: AVVIA_AI.bat (Windows) oppure AVVIA_AI_linux.sh (Linux).
"""
import ast
import builtins
import hashlib
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from xml.etree import ElementTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comune import *  # noqa: E402,F403

# input finti usati per provare i programmi che chiedono dati all'utente (prima numeri, poi parole)
INPUT_DI_PROVA = [
    ["5", "3", "8", "2", "0", "1", "4", "0", "stop", "STOP", "fine", "n", "no", "esci", "q", "x", "0"],
    ["casa", "Albero", "mela", "cane", "pera", "STOP", "a", "c", "stop", "fine", "n", "no", "0", "esci", "q", "x"],
]

# errori che indicano sempre un programma sbagliato (non dipendono dagli input di prova)
ERRORI_SEMPRE_GRAVI = {"NameError", "UnboundLocalError", "TypeError", "AttributeError",
                       "SyntaxError", "IndentationError", "TabError", "ImportError",
                       "ModuleNotFoundError", "RecursionError"}

ESTENSIONI_FASTA = (".fa", ".fasta", ".fna", ".faa")
MARCA = "@@@FINE_PREFISSO@@@"


class Interrotto(Exception):
    """L'utente ha premuto CTRL+C durante la generazione."""


# ================================================================ server AI

class ServerAI:
    def __init__(self, modello, contesto, config):
        self.modello = modello
        self.contesto = contesto
        self.config = config
        self.processo = None
        self.url = None
        self._job = None
        self._log = None
        self.cache_pronta = threading.Event()

    def _argomenti(self, porta, completi=True):
        argomenti = [ESEGUIBILE_SERVER, "-m", self.modello["percorso"], "-c", str(self.contesto),
                     "--host", "127.0.0.1", "--port", str(porta)]
        if completi:
            argomenti += ["-np", "1", "--no-webui", "--cache-ram", "0", "--jinja",
                          "--slot-save-path", CARTELLA_CACHE]
            argomenti += [str(a) for a in self.config.get("argomenti_extra_server", [])]
        return argomenti

    def avvia(self):
        os.makedirs(CARTELLA_LOG, exist_ok=True)
        os.makedirs(CARTELLA_CACHE, exist_ok=True)
        for completi in (True, False):
            porta = porta_libera()
            self.url = "http://127.0.0.1:" + str(porta)
            self._avvia_processo(self._argomenti(porta, completi))
            esito = self._attendi_pronto()
            if esito == "pronto":
                return True
            testo_log = self.coda_log()
            if completi and ("invalid argument" in testo_log or "unknown argument" in testo_log
                             or "error: " in testo_log):
                avviso("Il motore non accetta alcune opzioni, riprovo con le impostazioni minime...")
                continue
            break
        errore("Il motore AI non si è avviato.")
        codice = self.processo.poll() if self.processo else None
        if codice in (3221225781, -1073741515):
            info("Manca una libreria di Windows (Visual C++). Soluzione: avvia di nuovo")
            info("PREPARA_CHIAVETTA.bat su un PC con internet: copia le librerie mancanti.")
        else:
            info("Ultime righe del registro (" + os.path.join(CARTELLA_LOG, "server.log") + "):")
            for r in self.coda_log().splitlines()[-8:]:
                info(C.DIM + r + C.RESET)
        return False

    def _avvia_processo(self, argomenti):
        self.ferma()
        self._log = open(os.path.join(CARTELLA_LOG, "server.log"), "w", encoding="utf-8", errors="replace")
        opzioni = {}
        ambiente = dict(os.environ)
        if WINDOWS:
            # gruppo separato: CTRL+C ferma solo la risposta, non il motore
            opzioni["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            ambiente["LD_LIBRARY_PATH"] = CARTELLA_LLAMA + os.pathsep + ambiente.get("LD_LIBRARY_PATH", "")
            opzioni["preexec_fn"] = _muori_insieme_al_padre
        self.processo = subprocess.Popen(argomenti, stdout=self._log, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL, cwd=CARTELLA_LLAMA, env=ambiente,
                                         **opzioni)
        self._job = lega_al_processo(self.processo)

    def _attendi_pronto(self):
        inizio = time.time()
        giri = "|/-\\"
        n = 0
        while time.time() - inizio < 3600:
            if self.processo.poll() is not None:
                print()
                return "morto"
            try:
                with APRI_LOCALE(self.url + "/health", timeout=3) as r:
                    if r.status == 200:
                        print("\r" + " " * 70 + "\r", end="")
                        return "pronto"
            except (urllib.error.URLError, OSError, ValueError):
                pass
            print("\r      " + giri[n % 4] + " Carico il modello in memoria... " + durata(time.time() - inizio) + "   ",
                  end="", flush=True)
            n += 1
            time.sleep(0.5)
        print()
        return "tempo"

    def coda_log(self):
        try:
            with open(os.path.join(CARTELLA_LOG, "server.log"), "r", encoding="utf-8", errors="replace") as f:
                return f.read()[-6000:]
        except OSError:
            return ""

    def ferma(self):
        if self.processo and self.processo.poll() is None:
            self.processo.terminate()
            try:
                self.processo.wait(8)
            except subprocess.TimeoutExpired:
                self.processo.kill()
        self.processo = None
        if self._log:
            self._log.close()
            self._log = None

    # ------------------------------------------------------------ richieste

    def richiesta_json(self, percorso, dati=None, timeout=7200):
        corpo = json.dumps(dati).encode("utf-8") if dati is not None else None
        req = urllib.request.Request(self.url + percorso, data=corpo,
                                     headers={"Content-Type": "application/json"})
        with APRI_LOCALE(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def preriscalda(self, messaggi_fissi):
        """Mentre l'utente scrive, l'AI legge già regole ed esempi (e salva il lavoro sulla chiavetta)."""
        try:
            testo = self.richiesta_json("/apply-template", {
                "messages": messaggi_fissi + [{"role": "user", "content": MARCA}],
                "chat_template_kwargs": {"enable_thinking": bool(self.config.get("ragionamento"))},
            }, timeout=120)["prompt"]
            prefisso = testo[:testo.index(MARCA)]
            impronta = hashlib.sha1((self.modello["file"] + str(self.modello.get("dimensione")) + "|"
                                     + str(self.contesto) + "|" + prefisso).encode("utf-8")).hexdigest()[:16]
            nome_cache = "prefisso_" + impronta + ".bin"
            if os.path.exists(os.path.join(CARTELLA_CACHE, nome_cache)):
                try:
                    self.richiesta_json("/slots/0?action=restore", {"filename": nome_cache}, timeout=600)
                    return
                except (urllib.error.URLError, OSError, ValueError):
                    pass
            self.richiesta_json("/completion", {"prompt": prefisso, "n_predict": 1, "cache_prompt": True,
                                                "temperature": 0}, timeout=7200)
            self.richiesta_json("/slots/0?action=save", {"filename": nome_cache}, timeout=600)
            for vecchio in os.listdir(CARTELLA_CACHE):  # tengo solo la cache attuale
                if vecchio.startswith("prefisso_") and vecchio != nome_cache:
                    try:
                        os.remove(os.path.join(CARTELLA_CACHE, vecchio))
                    except OSError:
                        pass
        except Exception:
            pass  # la cache serve solo a fare prima: se non va, pazienza
        finally:
            self.cache_pronta.set()

    def genera(self, messaggi, fase="scrivendo il programma"):
        """Manda la richiesta e mostra la risposta mentre arriva. Restituisce il testo."""
        ragiona = bool(self.config.get("ragionamento"))
        max_token = int(self.config.get("max_token_risposta", 3000)) + (6000 if ragiona else 0)
        corpo = {
            "messages": messaggi,
            "stream": True,
            "temperature": float(self.config.get("temperatura", 0.3)),
            "top_p": 0.9,
            "top_k": 40,
            "min_p": 0.05,
            "max_tokens": max_token,
            "cache_prompt": True,
            "chat_template_kwargs": {"enable_thinking": ragiona},
        }
        req = urllib.request.Request(self.url + "/v1/chat/completions", data=json.dumps(corpo).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        coda = queue.Queue()
        contenitore = {}
        lettore = threading.Thread(target=_leggi_stream, args=(req, coda, contenitore), daemon=True)
        lettore.start()

        inizio = time.time()
        testo = ""
        pensieri = 0
        statistiche = None
        fine = None
        scrivendo = False
        giri = "|/-\\"
        n = 0
        try:
            while True:
                try:
                    tipo, dato = coda.get(timeout=0.4)
                except queue.Empty:
                    if not scrivendo:
                        stato = ("Sto ragionando (" + str(pensieri) + " parole)") if pensieri else "Sto leggendo l'esercizio"
                        print("\r      " + giri[n % 4] + " " + stato + "... " + durata(time.time() - inizio) + "    ",
                              end="", flush=True)
                        n += 1
                    continue
                if tipo == "errore":
                    raise dato
                if tipo == "fine":
                    break
                if dato.get("timings"):
                    statistiche = dato["timings"]
                for scelta in dato.get("choices", []):
                    delta = scelta.get("delta") or {}
                    if delta.get("reasoning_content"):
                        pensieri += 1
                    pezzo = delta.get("content")
                    if pezzo:
                        if not scrivendo:
                            scrivendo = True
                            print("\r" + " " * 70 + "\r      L'AI sta " + fase + " (" + durata(time.time() - inizio)
                                  + " per leggere):\n" + C.DIM, flush=True)
                        testo += pezzo
                        print(pezzo, end="", flush=True)
                    if scelta.get("finish_reason"):
                        fine = scelta["finish_reason"]
        except KeyboardInterrupt:
            chiudi_risposta(contenitore)
            print(C.RESET)
            raise Interrotto()
        print(C.RESET)
        if statistiche and statistiche.get("predicted_per_second"):
            info(C.DIM + "Tempo totale: " + durata(time.time() - inizio) + "  -  velocità: %.1f token/s"
                 % statistiche["predicted_per_second"] + C.RESET)
        if fine == "length":
            avviso("La risposta è stata tagliata perché troppo lunga.")
        return testo


def _leggi_stream(req, coda, contenitore):
    try:
        risposta = APRI_LOCALE(req, timeout=None)
        contenitore["risposta"] = risposta
        for grezza in risposta:
            r = grezza.decode("utf-8", "replace").strip()
            if not r.startswith("data:"):
                continue
            dato = r[5:].strip()
            if dato == "[DONE]":
                break
            oggetto = json.loads(dato)
            if "error" in oggetto:
                raise RuntimeError(str(oggetto["error"].get("message", oggetto["error"])))
            coda.put(("dati", oggetto))
        coda.put(("fine", None))
    except Exception as e:  # noqa: BLE001
        if isinstance(e, urllib.error.HTTPError):
            try:
                e = RuntimeError(e.read().decode("utf-8", "replace")[:500])
            except Exception:
                pass
        coda.put(("errore", e))


def chiudi_risposta(contenitore):
    """Chiude la connessione: così il motore smette di scrivere."""
    try:
        contenitore["risposta"].fp.raw._sock.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        contenitore["risposta"].close()
    except Exception:
        pass


def porta_libera():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _muori_insieme_al_padre():
    try:
        import ctypes
        import signal
        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG
    except Exception:
        pass


def lega_al_processo(processo):
    """Windows: se questa finestra si chiude (anche dalla X) il motore si chiude con lei."""
    if not WINDOWS:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.windll.kernel32
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]

        class BASE(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(nome, ctypes.c_ulonglong) for nome in
                        ("Read", "Write", "Other", "ReadBytes", "WriteBytes", "OtherBytes")]

        class ESTESA(ctypes.Structure):
            _fields_ = [("Base", BASE), ("Io", IO), ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        job = k32.CreateJobObjectW(None, None)
        limiti = ESTESA()
        limiti.Base.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        k32.SetInformationJobObject(job, 9, ctypes.byref(limiti), ctypes.sizeof(limiti))
        k32.AssignProcessToJobObject(job, int(processo._handle))
        return job
    except Exception:
        return None


# ================================================================ modelli

def modelli_installati():
    elenco = leggi_json(FILE_MODELLI, {}).get("modelli", [])
    pronti = []
    for m in elenco:
        percorso = os.path.join(CARTELLA_MODELLI, m["file"])
        if os.path.isfile(percorso):
            m = dict(m)
            m["percorso"] = percorso
            pronti.append(m)
    return pronti


def scegli_modello(config, installati, forzato=None):
    """Sceglie il modello più bravo che entra nella RAM libera di questo PC."""
    totale, libera = memoria_gb()
    scelta = forzato or config.get("modello", "auto")
    regole = {m["id"]: m for m in config["modelli"]}
    if scelta != "auto":
        for m in installati:
            if m["id"] == scelta:
                return m, totale, libera
        avviso("Il modello '" + scelta + "' non è sulla chiavetta: scelgo in automatico.")
    ordine = [r["id"] for r in config["modelli"]]  # dal più grande al più piccolo
    installati = sorted(installati, key=lambda m: ordine.index(m["id"]) if m["id"] in ordine else 99)
    if libera is None:
        libera_stimata = 3.0
    else:
        libera_stimata = libera
    for m in installati:
        minimo = regole.get(m["id"], {}).get("ram_libera_minima_gb", 0)
        if libera_stimata >= minimo:
            return m, totale, libera
    return installati[-1], totale, libera


# ================================================================ esempi e richiesta

def leggi_testo_file(percorso, limite=None):
    for codifica in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(percorso, "r", encoding=codifica) as f:
                return f.read(limite) if limite else f.read()
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def carica_esempi():
    esempi = []
    if not os.path.isdir(CARTELLA_ESEMPI):
        return esempi
    for nome in sorted(os.listdir(CARTELLA_ESEMPI)):
        cartella = os.path.join(CARTELLA_ESEMPI, nome)
        if not os.path.isdir(cartella):
            continue
        istruzioni = programma = None
        dati = []
        for f in sorted(os.listdir(cartella)):
            percorso = os.path.join(cartella, f)
            basso = f.lower()
            if not os.path.isfile(percorso) or basso.startswith("leggimi"):
                continue
            if basso.startswith("istruzion") or basso.startswith("testo") or basso.startswith("consegna"):
                istruzioni = percorso
            elif basso.endswith(".py") or (basso.startswith("programma") or basso.startswith("soluzione")):
                if programma is None or basso.endswith(".py"):
                    programma = percorso
            else:
                dati.append(percorso)
        if istruzioni and programma:
            esempi.append({
                "nome": nome,
                "utente": messaggio_utente(leggi_testo_file(istruzioni), dati),
                "codice": leggi_testo_file(programma).strip(),
            })
    return esempi


def anteprima_file(percorso):
    """Descrizione breve di un file di dati, da far vedere all'AI."""
    nome = os.path.basename(percorso)
    try:
        grandezza = os.path.getsize(percorso)
    except OSError:
        grandezza = 0
    testo = leggi_testo_file(percorso, 300000)
    righe = testo.splitlines()
    descrizione = "- " + nome
    if not righe:
        return descrizione + " (file vuoto o non di testo)"
    if nome.lower().endswith(ESTENSIONI_FASTA):
        intestazioni = [r.strip() for r in righe if r.startswith(">")][:6]
        descrizione += " (file FASTA, " + dimensione(grandezza) + "). Righe di intestazione trovate: " + ", ".join(intestazioni)
        descrizione += "\nPrime righe:\n" + "\n".join(r[:120] for r in righe[:3])
        return descrizione
    if grandezza < 5_000_000:
        descrizione += " (" + str(len(leggi_testo_file(percorso).splitlines())) + " righe"
    else:
        descrizione += " (file grande, " + dimensione(grandezza)
    prima = righe[0]
    separatori = {";": prima.count(";"), ",": prima.count(","), "\\t (tabulazione)": prima.count("\t")}
    migliore = max(separatori, key=separatori.get)
    if separatori[migliore] > 0:
        descrizione += ', colonne separate da "' + migliore + '"'
    descrizione += "). Prime righe:\n" + "\n".join(r[:200] for r in righe[:6])
    return descrizione


def messaggio_utente(istruzioni, file_dati):
    testo = "ESERCIZIO:\n" + istruzioni.strip()
    if file_dati:
        testo += "\n\nFILE A DISPOSIZIONE (sono nella stessa cartella del programma: aprili usando solo il nome):"
        for percorso in file_dati:
            testo += "\n" + anteprima_file(percorso)
    return testo


def blocco_codice(codice):
    return "```python\n" + codice.strip() + "\n```"


def messaggi_fissi(stile, esempi):
    messaggi = [{"role": "system", "content": stile.strip()}]
    for e in esempi:
        messaggi.append({"role": "user", "content": e["utente"]})
        messaggi.append({"role": "assistant", "content": blocco_codice(e["codice"])})
    return messaggi


def scegli_esempi(esempi, richiesta, limite_caratteri):
    """Se gli esempi sono troppi, tiene quelli che somigliano di più all'esercizio."""
    def peso(e):
        return len(e["utente"]) + len(e["codice"])

    if sum(peso(e) for e in esempi) <= limite_caratteri:
        return esempi
    parole = set(re.findall(r"[a-zàèéìòù]{4,}", richiesta.lower()))

    def somiglianza(e):
        altre = set(re.findall(r"[a-zàèéìòù]{4,}", (e["utente"] + e["codice"]).lower()))
        return len(parole & altre) / (1 + len(altre) ** 0.5)

    scelti, totale = [], 0
    for e in sorted(esempi, key=somiglianza, reverse=True):
        if totale + peso(e) <= limite_caratteri or not scelti:
            scelti.append(e)
            totale += peso(e)
    return [e for e in esempi if e in scelti]  # stesso ordine di sempre


def estrai_codice(testo):
    blocchi = re.findall(r"```[ \t]*(?:python3?|py)?[ \t]*\r?\n(.*?)```", testo, re.S | re.I)
    if blocchi:
        return max(blocchi, key=len).strip("\n")
    aperto = re.search(r"```[ \t]*(?:python3?|py)?[ \t]*\r?\n(.*)", testo, re.S | re.I)
    if aperto:
        return aperto.group(1).strip("\n")
    return testo.strip("\n")


# ================================================================ controlli automatici

def nomi_non_definiti(albero):
    definiti = set(dir(builtins)) | {"__name__", "__file__", "__doc__"}
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, (ast.Store, ast.Del)):
            definiti.add(nodo.id)
        elif isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definiti.add(nodo.name)
        elif isinstance(nodo, ast.arg):
            definiti.add(nodo.arg)
        elif isinstance(nodo, (ast.Import, ast.ImportFrom)):
            for alias in nodo.names:
                if alias.name == "*":
                    return []
                definiti.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(nodo, ast.ExceptHandler) and nodo.name:
            definiti.add(nodo.name)
        elif hasattr(ast, "MatchAs") and isinstance(nodo, (ast.MatchAs, ast.MatchStar)) and nodo.name:
            definiti.add(nodo.name)
    problemi = []
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Name) and isinstance(nodo.ctx, ast.Load) and nodo.id not in definiti:
            problemi.append((nodo.lineno, nodo.id))
    return sorted(set(problemi))


FUNZIONI_DI_PYTHON = {"max", "min", "sum", "len", "list", "dict", "str", "int", "float", "input", "type"}


def errori_tipici(albero):
    """Errori da principiante che non sempre si vedono provando il programma."""
    assegnati = {n.id for n in ast.walk(albero) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    for nodo in ast.walk(albero):
        if isinstance(nodo, (ast.For, ast.comprehension)) and isinstance(nodo.iter, ast.Attribute) \
                and nodo.iter.attr in ("items", "keys", "values", "split", "readlines"):
            return ("Alla riga " + str(nodo.iter.lineno) + " dopo ." + nodo.iter.attr
                    + " mancano le parentesi: devi scrivere ." + nodo.iter.attr + "()")
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute) and nodo.func.attr == "update" \
                and nodo.args and isinstance(nodo.args[0], ast.Set):
            return ("Alla riga " + str(nodo.lineno) + " update({a, b}) passa un set e non un dictionary: "
                    "per inserire una chiave scrivi dizionario[chiave] = valore")
        operandi = []
        if isinstance(nodo, ast.Compare):
            operandi = [nodo.left] + list(nodo.comparators)
        elif isinstance(nodo, ast.BinOp):
            operandi = [nodo.left, nodo.right]
        for op in operandi:
            if isinstance(op, ast.Name) and op.id in FUNZIONI_DI_PYTHON and op.id not in assegnati:
                return ("Alla riga " + str(op.lineno) + " usi '" + op.id + "' come se fosse una variabile, ma non le dai "
                        "mai un valore (in Python " + op.id + " è una funzione). Usa una variabile con un altro "
                        "nome (per esempio massimo) e dalle un valore iniziale.")
    return None


def librerie_esterne(albero):
    standard = getattr(sys, "stdlib_module_names", None)
    if not standard:
        return []
    esterne = []
    for nodo in ast.walk(albero):
        nomi = []
        if isinstance(nodo, ast.Import):
            nomi = [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0 and nodo.module:
            nomi = [nodo.module]
        for nome in nomi:
            radice = nome.split(".")[0]
            if radice not in standard and radice not in esterne:
                esterne.append(radice)
    return esterne


def controlla_programma(codice, file_dati, secondi):
    """Restituisce None se va tutto bene, altrimenti la descrizione del problema (per l'AI)."""
    if not codice.strip():
        return "Non hai scritto il programma. Scrivi il programma Python completo dentro un blocco ```python."
    try:
        albero = ast.parse(codice)
        compile(codice, "programma.py", "exec")
    except SyntaxError as e:
        riga_errata = (e.text or "").rstrip()
        return ("Il programma ha un errore di sintassi alla riga " + str(e.lineno) + ": " + str(e.msg)
                + ("\nRiga: " + riga_errata if riga_errata else ""))
    esterne = librerie_esterne(albero)
    if esterne:
        return ("Il programma usa librerie che non sono installate: " + ", ".join(esterne)
                + ". Riscrivilo usando solo Python base e la libreria standard.")
    mancanti = nomi_non_definiti(albero)
    if mancanti:
        elenco = ", ".join("'" + nome + "' (riga " + str(n) + ")" for n, nome in mancanti[:6])
        return "Nel programma usi dei nomi che non sono mai stati definiti: " + elenco + "."
    tipico = errori_tipici(albero)
    if tipico:
        return tipico
    return prova_programma(codice, file_dati, secondi)


def prova_programma(codice, file_dati, secondi):
    """Esegue il programma per davvero (in una cartella temporanea, con input finti)."""
    gruppi = INPUT_DI_PROVA if "input(" in codice else [[]]
    for input_finti in gruppi:
        problema = _prova_con_input(codice, file_dati, secondi, input_finti)
        if problema:
            return problema
    return None


def _prova_con_input(codice, file_dati, secondi, input_finti):
    usa_input = bool(input_finti)
    cartella = os.path.join(CARTELLA_TMP, "prova_" + str(os.getpid()) + "_" + str(int(time.time() * 1000)))
    os.makedirs(cartella, exist_ok=True)
    try:
        for f in file_dati:
            shutil.copy2(f, os.path.join(cartella, os.path.basename(f)))
        with open(os.path.join(cartella, "programma.py"), "w", encoding="utf-8") as f:
            f.write(codice)
        ambiente = dict(os.environ)
        ambiente["PYTHONIOENCODING"] = "utf-8"
        ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
        uscita_percorso = os.path.join(cartella, "_uscita.txt")
        with open(uscita_percorso, "w", encoding="utf-8") as uscita:
            try:
                completato = subprocess.run([sys.executable, "-B", "programma.py"], cwd=cartella,
                                            input="\n".join(input_finti) + "\n", stdout=uscita,
                                            stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                            errors="replace", timeout=secondi, env=ambiente)
            except subprocess.TimeoutExpired:
                if file_dati:
                    return None  # con file grandi può volerci tempo: non è per forza un errore
                return ("Ho provato il programma ma dopo " + str(secondi) + " secondi non era ancora finito: "
                        "probabilmente c'è un ciclo infinito (un while che non si ferma mai).")
        errori = completato.stderr or ""
        if completato.returncode == 0 or "Traceback" not in errori:
            return None
        ultima = [r for r in errori.strip().splitlines() if r.strip()][-1]
        tipo = ultima.split(":")[0].strip().split(".")[-1]
        if tipo == "EOFError":
            return None  # ha finito gli input di prova: va bene
        if tipo == "FileNotFoundError" and not file_dati:
            return None  # non ho i file per provarlo
        if tipo not in ERRORI_SEMPRE_GRAVI and usa_input and tipo != "FileNotFoundError":
            return None  # potrebbe dipendere dagli input di prova
        dettaglio = "\n".join(errori.strip().splitlines()[-12:]).replace(cartella + os.sep, "")
        testo = "Ho eseguito il programma e si blocca con questo errore:\n" + dettaglio
        if usa_input:
            testo += "\n(come input ho scritto, in ordine: " + ", ".join(input_finti[:10]) + ", ...)"
        return testo
    finally:
        shutil.rmtree(cartella, ignore_errors=True)


# ================================================================ file dati

def xlsx_in_csv(percorso, destinazione):
    """Converte un file Excel in CSV con il ; (come fa Excel in italiano)."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(percorso) as z:
        nomi = z.namelist()
        condivise = []
        if "xl/sharedStrings.xml" in nomi:
            radice = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            for si in radice.iter(ns + "si"):
                condivise.append("".join(t.text or "" for t in si.iter(ns + "t")))
        fogli = sorted(n for n in nomi if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        foglio = "xl/worksheets/sheet1.xml" if "xl/worksheets/sheet1.xml" in nomi else fogli[0]
        radice = ElementTree.fromstring(z.read(foglio))
    righe = []
    for r in radice.iter(ns + "row"):
        celle = {}
        for c in r.iter(ns + "c"):
            rif = c.get("r", "")
            lettere = "".join(ch for ch in rif if ch.isalpha())
            colonna = 0
            for ch in lettere:
                colonna = colonna * 26 + (ord(ch.upper()) - 64)
            colonna = colonna - 1 if lettere else len(celle)
            tipo = c.get("t")
            v = c.find(ns + "v")
            valore = v.text if v is not None and v.text is not None else ""
            if tipo == "s" and valore:
                valore = condivise[int(valore)]
            elif tipo == "inlineStr":
                valore = "".join(t.text or "" for t in c.iter(ns + "t"))
            elif tipo == "b":
                valore = "TRUE" if valore == "1" else "FALSE"
            elif re.fullmatch(r"-?\d+\.0", valore):
                valore = valore[:-2]
            celle[colonna] = valore.replace("\n", " ")
        if celle:
            righe.append([celle.get(i, "") for i in range(max(celle) + 1)])
    codifica = "cp1252" if WINDOWS else "utf-8"
    with open(destinazione, "w", encoding=codifica, errors="replace") as f:
        for r in righe:
            f.write(";".join(r) + "\n")


def pulisci_percorso(testo):
    testo = testo.strip().strip('"').strip("'").strip()
    if testo.startswith("file://"):
        from urllib.parse import unquote
        testo = unquote(testo[7:])
    if not WINDOWS:
        testo = testo.replace("\\ ", " ")
    return testo


# ================================================================ interfaccia

def altro_input_in_arrivo():
    """Vero se l'utente ha incollato altro testo che deve ancora essere letto."""
    time.sleep(0.15)
    try:
        if WINDOWS:
            import msvcrt
            return msvcrt.kbhit()
        import select
        return bool(select.select([sys.stdin], [], [], 0)[0])
    except Exception:
        return False


def leggi_testo_lungo(invito):
    print(C.CIANO + invito + C.RESET)
    righe = []
    while True:
        try:
            r = input(C.BOLD + " > " + C.RESET if not righe else "   ")
        except EOFError:
            break
        if r.strip().upper() == "FINE":
            break
        if r.strip() == "":
            if not righe:
                continue
            if altro_input_in_arrivo():  # riga vuota dentro un testo incollato
                righe.append("")
                continue
            break
        righe.append(r.rstrip())
    return "\n".join(righe).strip()


def chiedi_file_dati(istruzioni):
    disponibili = []
    if os.path.isdir(CARTELLA_DATI):
        disponibili = [os.path.join(CARTELLA_DATI, f) for f in sorted(os.listdir(CARTELLA_DATI))
                       if os.path.isfile(os.path.join(CARTELLA_DATI, f)) and not f.lower().startswith("leggimi")]
    parla_di_file = re.search(r"\bfile\b|allegat|\.csv|\.txt|\.fa\b|\.fasta|\.vcf|\.xlsx", istruzioni, re.I)
    if not disponibili and not parla_di_file:
        return []
    print()
    print(C.CIANO + " L'esercizio usa dei file di dati (csv, txt, fasta, vcf, xlsx...)?" + C.RESET)
    info("Trascina qui il file dentro questa finestra e premi INVIO (un file alla volta).")
    if disponibili:
        info("Oppure scrivi il numero di un file della cartella 'dati':")
        for i, f in enumerate(disponibili, 1):
            info("   [" + str(i) + "] " + os.path.basename(f))
    info("Quando hai finito (o se non servono file) premi solo INVIO.")
    scelti = []
    while True:
        try:
            r = pulisci_percorso(input(C.BOLD + " file > " + C.RESET))
        except EOFError:
            break
        if not r:
            break
        percorso = None
        if r.isdigit() and 1 <= int(r) <= len(disponibili):
            percorso = disponibili[int(r) - 1]
        elif os.path.isfile(r):
            percorso = os.path.abspath(r)
        elif os.path.isfile(os.path.join(CARTELLA_DATI, r)):
            percorso = os.path.join(CARTELLA_DATI, r)
        if not percorso:
            avviso("Non trovo il file: " + r)
            continue
        if percorso not in scelti:
            scelti.append(percorso)
            ok("Aggiunto: " + os.path.basename(percorso))
    if parla_di_file and not scelti:
        info(C.DIM + "Nessun file: l'AI sceglierà lei un nome per il file (potrai cambiarlo dopo)." + C.RESET)
    return scelti


def crea_cartella_esercizio(istruzioni):
    prima = istruzioni.strip().splitlines()[0] if istruzioni.strip() else "esercizio"
    nome = re.sub(r"[^a-z0-9]+", "_", prima.lower()).strip("_")[:40] or "esercizio"
    base = os.path.join(CARTELLA_PROGRAMMI, datetime.now().strftime("%Y-%m-%d_%H-%M") + "_" + nome)
    cartella = base
    n = 2
    while os.path.exists(cartella):
        cartella = base + "_" + str(n)
        n += 1
    os.makedirs(cartella)
    return cartella


def prepara_file_dati(scelti, cartella):
    """Copia i file nella cartella del programma (e converte gli Excel in CSV)."""
    finali = []
    for percorso in scelti:
        nome = os.path.basename(percorso)
        if nome.lower().endswith((".xlsx", ".xlsm")):
            nuovo = os.path.join(cartella, os.path.splitext(nome)[0] + ".csv")
            try:
                xlsx_in_csv(percorso, nuovo)
                ok("Ho convertito " + nome + " in " + os.path.basename(nuovo) + " (separatore ;)")
                finali.append(nuovo)
                continue
            except Exception as e:  # noqa: BLE001
                avviso("Non riesco a convertire " + nome + " (" + str(e) + "): lo uso così com'è.")
        destinazione = os.path.join(cartella, nome)
        if os.path.abspath(percorso) != os.path.abspath(destinazione):
            shutil.copy2(percorso, destinazione)
        finali.append(destinazione)
    return finali


def salva_programma(cartella, codice):
    percorso = os.path.join(cartella, "programma.py")
    if os.path.exists(percorso):  # tengo la versione precedente
        n = 1
        while os.path.exists(os.path.join(cartella, "programma_v" + str(n) + ".py")):
            n += 1
        os.replace(percorso, os.path.join(cartella, "programma_v" + str(n) + ".py"))
    with open(percorso, "w", encoding="utf-8") as f:
        f.write(codice.rstrip() + "\n")
    return percorso


def mostra_codice(codice):
    print()
    riga("-")
    print(C.BOLD + C.VERDE + " PROGRAMMA" + C.RESET)
    riga("-")
    print(codice.rstrip())
    riga("-")


def copia_negli_appunti(percorso):
    try:
        if WINDOWS:
            ambiente = dict(os.environ)
            ambiente["FILE_DA_COPIARE"] = percorso
            r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                                "Set-Clipboard -Value (Get-Content -Raw -Encoding UTF8 -LiteralPath $env:FILE_DA_COPIARE)"],
                               env=ambiente, capture_output=True, timeout=30)
            if r.returncode == 0:
                return True
            with open(percorso, "r", encoding="utf-8") as f:
                testo = f.read()
            subprocess.run(["clip"], input=("﻿" + testo).encode("utf-16-le"), timeout=30, check=True)
            return True
        with open(percorso, "rb") as f:
            dati = f.read()
        for comando in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]):
            if shutil.which(comando[0]):
                subprocess.run(comando, input=dati, timeout=30, check=True)
                return True
    except Exception:
        pass
    return False


# esegue programma.py e, se si blocca, salva l'errore in un file (l'errore si vede comunque a schermo)
LANCIATORE = '''import runpy, sys, traceback
file_errori = sys.argv.pop(1)
sys.argv[0] = "programma.py"
try:
    runpy.run_path("programma.py", run_name="__main__")
except (KeyboardInterrupt, SystemExit):
    raise
except BaseException:
    with open(file_errori, "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    raise
'''


def esegui_per_utente(cartella):
    """Esegue il programma nella finestra: l'utente può scrivere gli input."""
    print()
    riga("-")
    print(C.BOLD + " ESECUZIONE DEL PROGRAMMA" + C.RESET + C.DIM + "   (CTRL+C per fermarlo)" + C.RESET)
    riga("-")
    os.makedirs(CARTELLA_TMP, exist_ok=True)
    lanciatore = os.path.join(CARTELLA_TMP, "lanciatore.py")
    file_errori = os.path.join(CARTELLA_TMP, "errore_programma.txt")
    with open(lanciatore, "w", encoding="utf-8") as f:
        f.write(LANCIATORE)
    if os.path.exists(file_errori):
        os.remove(file_errori)
    ambiente = dict(os.environ)
    ambiente["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        subprocess.run([sys.executable, "-B", lanciatore, file_errori], cwd=cartella, env=ambiente)
    except KeyboardInterrupt:
        print()
    riga("-")
    if os.path.exists(file_errori):
        errori = leggi_testo_file(file_errori).strip()
        righe = errori.splitlines()
        # tolgo le righe del lanciatore: all'AI interessa solo programma.py
        utili = [r for i, r in enumerate(righe) if not ("runpy" in r or "lanciatore.py" in r
                 or (i > 0 and ("runpy" in righe[i - 1] or "lanciatore.py" in righe[i - 1])))]
        return "\n".join(utili)
    return None


# ================================================================ programma principale

class Assistente:
    def __init__(self, server, config, stile, esempi, limite_esempi):
        self.server = server
        self.config = config
        self.stile = stile
        self.esempi = esempi
        self.limite = limite_esempi

    def fissi(self, richiesta):
        return messaggi_fissi(self.stile, scegli_esempi(self.esempi, richiesta, self.limite))

    def crea(self, testo_utente, file_dati, codice_precedente=None, modifica=None):
        """Genera il programma, lo controlla e se serve lo fa correggere."""
        fissi = self.fissi(testo_utente)
        messaggi = fissi + [{"role": "user", "content": testo_utente}]
        fase = "scrivendo il programma"
        if codice_precedente is not None:
            messaggi += [{"role": "assistant", "content": blocco_codice(codice_precedente)},
                         {"role": "user", "content": "Modifica il programma così:\n" + modifica
                          + "\n\nRiscrivi il programma COMPLETO, con lo stesso stile."}]
            fase = "modificando il programma"
        codice = estrai_codice(self.server.genera(messaggi, fase))
        tentativi = int(self.config.get("tentativi_correzione", 2))
        secondi = int(self.config.get("secondi_test", 20))
        problema = None
        for tentativo in range(tentativi + 1):
            print()
            print("      Controllo il programma (sintassi, nomi, prova di esecuzione)...", flush=True)
            problema = controlla_programma(codice, file_dati, secondi)
            if problema is None:
                ok("Controllo superato.")
                break
            prima_riga = problema.splitlines()[0]
            if tentativo == tentativi:
                avviso("Rimane un problema che non sono riuscito a correggere da solo:")
                info(C.DIM + problema.replace("\n", "\n      ") + C.RESET)
                break
            avviso(prima_riga)
            info("Lo faccio correggere all'AI (tentativo " + str(tentativo + 1) + " di " + str(tentativi) + ")...")
            correzione = fissi + [
                {"role": "user", "content": testo_utente},
                {"role": "assistant", "content": blocco_codice(codice)},
                {"role": "user", "content": problema + "\n\nCorreggi il problema e riscrivi il programma "
                 "COMPLETO (tutti i punti dell'esercizio), con lo stesso stile."},
            ]
            nuovo = estrai_codice(self.server.genera(correzione, "correggendo il programma"))
            if nuovo.strip():
                codice = nuovo
        return codice, problema


def banner():
    print()
    riga("=")
    print(C.BOLD + C.CIANO + "   AI PYTHON OFFLINE" + C.RESET + "  -  scrivi l'esercizio, ricevi il programma")
    riga("=")


def main():
    abilita_colori()
    titolo_finestra("AI Python Offline")
    banner()
    forzato = None
    if "--modello" in sys.argv:
        i = sys.argv.index("--modello")
        if i + 1 < len(sys.argv):
            forzato = sys.argv[i + 1]
    config = carica_config()
    installati = modelli_installati()
    if not os.path.isfile(ESEGUIBILE_SERVER) or not installati:
        errore("La chiavetta non è ancora pronta (manca il motore AI o il modello).")
        info("Avvia PREPARA_CHIAVETTA su un PC con internet (serve solo la prima volta).")
        return 1

    shutil.rmtree(CARTELLA_TMP, ignore_errors=True)
    modello, totale, libera = scegli_modello(config, installati, forzato)
    regola = next((m for m in config["modelli"] if m["id"] == modello["id"]), {})
    contesto = int(regola.get("contesto", 8192)) + (8192 if config.get("ragionamento") else 0)
    if totale:
        info("RAM del PC: %.1f GB (libera ora: %.1f GB)" % (totale, libera))
    info("Modello scelto: " + C.BOLD + modello.get("nome", modello["file"]) + C.RESET
         + " (" + modello["id"] + ", " + dimensione(modello.get("dimensione", 0)) + ")")
    info(C.DIM + "La prima volta dalla chiavetta il caricamento può durare qualche minuto." + C.RESET)

    server = ServerAI(modello, contesto, config)
    try:
        if not server.avvia():
            return 1
        ok("Motore AI pronto.")
        stile = leggi_testo_file(FILE_STILE)
        esempi = carica_esempi()
        info(C.DIM + "Esempi di stile caricati: " + str(len(esempi)) + " (cartella 'esempi')" + C.RESET)
        limite_esempi = int(regola.get("caratteri_esempi", config.get("caratteri_esempi", 11000)))
        assistente = Assistente(server, config, stile, esempi, limite_esempi)
        threading.Thread(target=server.preriscalda, args=(assistente.fissi(""),), daemon=True).start()
        ciclo_principale(assistente)
    except KeyboardInterrupt:
        print()
    finally:
        print()
        info("Chiudo il motore AI...")
        server.ferma()
        shutil.rmtree(CARTELLA_TMP, ignore_errors=True)
        ok("Fatto. Ora puoi chiudere la finestra e togliere la chiavetta.")
    return 0


def ciclo_principale(assistente):
    while True:
        print()
        riga("=")
        istruzioni = leggi_testo_lungo(" SCRIVI O INCOLLA IL TESTO DELL'ESERCIZIO\n"
                                       + C.RESET + C.DIM + " (quando hai finito premi INVIO su una riga vuota, "
                                       "oppure scrivi FINE. Per uscire chiudi la finestra o premi CTRL+C)")
        if not istruzioni:
            continue
        scelti = chiedi_file_dati(istruzioni)
        cartella = crea_cartella_esercizio(istruzioni)
        file_dati = prepara_file_dati(scelti, cartella)
        with open(os.path.join(cartella, "istruzioni.txt"), "w", encoding="utf-8") as f:
            f.write(istruzioni + "\n")
        testo_utente = messaggio_utente(istruzioni, file_dati)
        print()
        info("Ci vorrà qualche minuto: non chiudere la finestra." + C.DIM + " (CTRL+C per annullare)" + C.RESET)
        try:
            codice, problema = assistente.crea(testo_utente, file_dati)
        except (Interrotto, Exception) as e:  # noqa: BLE001
            if isinstance(e, Interrotto):
                avviso("Annullato.")
            else:
                errore("Errore durante la generazione: " + str(e))
            shutil.rmtree(cartella, ignore_errors=True)
            continue
        percorso = salva_programma(cartella, codice)
        mostra_codice(codice)
        ok("Salvato in: " + percorso)
        menu_programma(assistente, testo_utente, file_dati, cartella, codice)


def menu_programma(assistente, testo_utente, file_dati, cartella, codice):
    modifiche = []
    while True:
        print()
        print(C.CIANO + " Cosa vuoi fare?" + C.RESET)
        info("[1] Esegui il programma")
        info("[2] Chiedi una modifica o segnala un errore")
        info("[3] Copia il programma negli appunti")
        info("[4] Mostra di nuovo il programma")
        info("[5] Nuovo esercizio")
        info("[0] Esci")
        try:
            scelta = input(C.BOLD + " scelta > " + C.RESET).strip()
        except EOFError:
            raise KeyboardInterrupt
        modifica = None
        if scelta == "1":
            errori = esegui_per_utente(cartella)
            if errori:
                try:
                    risposta = input(" Il programma si è bloccato. Lo faccio correggere all'AI? (S/n) ").strip().lower()
                except EOFError:
                    risposta = "n"
                if risposta in ("", "s", "si", "sì", "y"):
                    modifica = "Quando lo eseguo si blocca con questo errore:\n" + errori
        elif scelta == "2":
            modifica = leggi_testo_lungo(" Scrivi cosa vuoi cambiare (o incolla l'errore). INVIO su riga vuota per finire:")
        elif scelta == "3":
            if copia_negli_appunti(os.path.join(cartella, "programma.py")):
                ok("Copiato! Ora puoi incollarlo dove vuoi (CTRL+V).")
            else:
                avviso("Non riesco a copiare: apri il file " + os.path.join(cartella, "programma.py"))
        elif scelta == "4":
            mostra_codice(codice)
        elif scelta == "5":
            return
        elif scelta == "0":
            raise KeyboardInterrupt
        if modifica:
            testo_completo = testo_utente + "".join("\n\nIn più: " + m for m in modifiche)
            try:
                nuovo, problema = assistente.crea(testo_completo, file_dati, codice, modifica)
            except Interrotto:
                avviso("Annullato.")
                continue
            except Exception as e:  # noqa: BLE001
                errore("Errore durante la generazione: " + str(e))
                continue
            if not modifica.startswith("Quando lo eseguo si blocca"):
                modifiche.append(modifica)
            codice = nuovo
            percorso = salva_programma(cartella, codice)
            mostra_codice(codice)
            ok("Salvato in: " + percorso + "  (la versione prima è in programma_v*.py)")


if __name__ == "__main__":
    sys.exit(main())
