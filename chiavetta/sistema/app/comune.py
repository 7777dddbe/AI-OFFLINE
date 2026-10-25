"""Cose in comune tra assistente.py e prepara.py: cartelle, colori, configurazione, RAM."""
import json
import os
import sys
import urllib.request

WINDOWS = os.name == "nt"

APP = os.path.dirname(os.path.abspath(__file__))  # chiavetta/sistema/app
SISTEMA = os.path.dirname(APP)                   # chiavetta/sistema
RADICE = os.path.dirname(SISTEMA)                # chiavetta/

CARTELLA_ESEMPI = os.path.join(RADICE, "esempi")
CARTELLA_PROGRAMMI = os.path.join(RADICE, "programmi")
CARTELLA_DATI = os.path.join(RADICE, "dati")
CARTELLA_MODELLI = os.path.join(SISTEMA, "modelli")
CARTELLA_CACHE = os.path.join(SISTEMA, "cache")
CARTELLA_LOG = os.path.join(SISTEMA, "log")
CARTELLA_TMP = os.path.join(SISTEMA, "tmp")
CARTELLA_LLAMA_WIN = os.path.join(SISTEMA, "llama-win")
CARTELLA_LLAMA_LINUX = os.path.join(SISTEMA, "llama-linux")
# AI_OFFLINE_LLAMA: su Linux, se la chiavetta non permette di eseguire file, lo script di avvio usa una copia temporanea
CARTELLA_LLAMA = os.environ.get("AI_OFFLINE_LLAMA") or (CARTELLA_LLAMA_WIN if WINDOWS else CARTELLA_LLAMA_LINUX)
FILE_MODELLI = os.path.join(CARTELLA_MODELLI, "modelli.json")
FILE_CONFIG = os.path.join(APP, "config.json")
FILE_STILE = os.path.join(APP, "stile.txt")

ESEGUIBILE_SERVER = os.path.join(CARTELLA_LLAMA, "llama-server.exe" if WINDOWS else "llama-server")


# ---------------------------------------------------------------- colori

class C:
    RESET = BOLD = DIM = ROSSO = VERDE = GIALLO = BLU = CIANO = ""


def abilita_colori():
    """Attiva i colori ANSI (su Windows 10+ vanno abilitati a mano)."""
    if not sys.stdout.isatty():
        return
    if WINDOWS:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            modo = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(modo)):
                return
            if not kernel32.SetConsoleMode(handle, modo.value | 0x0004):
                return
        except Exception:
            return
    C.RESET, C.BOLD, C.DIM = "\033[0m", "\033[1m", "\033[2m"
    C.ROSSO, C.VERDE, C.GIALLO = "\033[91m", "\033[92m", "\033[93m"
    C.BLU, C.CIANO = "\033[94m", "\033[96m"


def titolo_finestra(testo):
    if WINDOWS:
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(testo)
        except Exception:
            pass


def riga(car="=", n=64):
    print(C.DIM + car * n + C.RESET)


def ok(testo):
    print(C.VERDE + " [OK] " + C.RESET + testo)


def avviso(testo):
    print(C.GIALLO + " [!]  " + C.RESET + testo)


def errore(testo):
    print(C.ROSSO + " [X]  " + C.RESET + testo)


def info(testo):
    print("      " + testo)


def durata(secondi):
    secondi = int(secondi)
    if secondi < 60:
        return str(secondi) + " s"
    return str(secondi // 60) + " min " + str(secondi % 60).zfill(2) + " s"


def dimensione(byte):
    if byte >= 1024 ** 3:
        return "%.1f GB" % (byte / 1024 ** 3)
    return "%.0f MB" % (byte / 1024 ** 2)


# ---------------------------------------------------------------- file json

def leggi_json(percorso, predefinito=None):
    try:
        with open(percorso, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return predefinito


def scrivi_json(percorso, dati):
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    temporaneo = percorso + ".tmp"
    with open(temporaneo, "w", encoding="utf-8") as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)
    os.replace(temporaneo, percorso)


def carica_config():
    config = leggi_json(FILE_CONFIG)
    if not config:
        raise SystemExit("File di configurazione mancante o rovinato: " + FILE_CONFIG)
    return config


# ---------------------------------------------------------------- RAM

def memoria_gb():
    """Restituisce (RAM totale, RAM libera) in GB, oppure (None, None)."""
    try:
        if WINDOWS:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stato = MEMORYSTATUSEX()
            stato.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stato))
            return stato.ullTotalPhys / 1024 ** 3, stato.ullAvailPhys / 1024 ** 3
        valori = {}
        with open("/proc/meminfo") as f:
            for r in f:
                nome, valore = r.split(":", 1)
                valori[nome] = int(valore.split()[0]) * 1024
        return valori["MemTotal"] / 1024 ** 3, valori.get("MemAvailable", valori["MemFree"]) / 1024 ** 3
    except Exception:
        return None, None


# ---------------------------------------------------------------- rete locale

# per parlare con il server locale non bisogna MAI passare dal proxy della scuola/ufficio
APRI_LOCALE = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
