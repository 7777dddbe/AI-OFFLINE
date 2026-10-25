"""Prepara la chiavetta: scarica il motore AI (llama.cpp) e i modelli. Serve internet, solo la prima volta.

Avvio: PREPARA_CHIAVETTA.bat (Windows) oppure PREPARA_CHIAVETTA_linux.sh (Linux).
Opzioni: --aggiorna (riscarica il motore AI anche se c'è già), --si (non fa domande), --senza-test
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comune import *  # noqa: E402,F403

INTESTAZIONI = {"User-Agent": "ai-offline-chiavetta/1.0"}
GITHUB_RELEASE_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15"
GITHUB_RELEASE_WEB = "https://github.com/ggml-org/llama.cpp/releases"
HF = "https://huggingface.co"

MOTORI = {
    "win": {"cartella": CARTELLA_LLAMA_WIN, "schema": r"bin-win-cpu-x64\.zip$", "eseguibile": "llama-server.exe"},
    "linux": {"cartella": CARTELLA_LLAMA_LINUX, "schema": r"bin-ubuntu-x64\.tar\.gz$", "eseguibile": "llama-server"},
}

# librerie di Visual C++ che il motore potrebbe chiedere (si possono copiare accanto al programma)
DLL_VISUAL_CPP = ["msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll", "msvcp140_atomic_wait.dll",
                  "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll", "concrt140.dll",
                  "vcomp140.dll"]


# ================================================================ rete

def scarica_testo(url, timeout=60):
    req = urllib.request.Request(url, headers=INTESTAZIONI)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace"), r.geturl()


def scarica_json(url):
    return json.loads(scarica_testo(url)[0])


def scarica_file(url, destinazione, grandezza=None, sha256=None, etichetta=""):
    """Scarica con barra di avanzamento. Se si interrompe, rilanciando riparte da dove era arrivato."""
    if os.path.isfile(destinazione) and (not grandezza or os.path.getsize(destinazione) == grandezza):
        ok(etichetta + ": già presente")
        return
    os.makedirs(os.path.dirname(destinazione), exist_ok=True)
    parziale = destinazione + ".parziale"
    for tentativo in range(1, 7):
        try:
            _scarica_una_volta(url, parziale, grandezza, sha256, etichetta)
            os.replace(parziale, destinazione)
            return
        except (urllib.error.URLError, OSError, ConnectionError, TimeoutError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 404):
                raise
            print()
            avviso("Connessione interrotta (" + str(e) + "). Riprovo tra " + str(5 * tentativo) + " secondi...")
            time.sleep(5 * tentativo)
    raise RuntimeError("download non riuscito dopo vari tentativi: " + url)


def _scarica_una_volta(url, parziale, grandezza, sha256, etichetta):
    gia = os.path.getsize(parziale) if os.path.isfile(parziale) else 0
    if grandezza and gia > grandezza:
        os.remove(parziale)
        gia = 0
    impronta = hashlib.sha256()
    if gia and sha256:
        with open(parziale, "rb") as f:
            for pezzo in iter(lambda: f.read(8 * 1024 * 1024), b""):
                impronta.update(pezzo)
    if grandezza and gia == grandezza:  # era già tutto scaricato: resta solo il controllo
        if sha256 and impronta.hexdigest().lower() != sha256.lower():
            os.remove(parziale)
            raise ConnectionError("file rovinato, lo riscarico")
        return
    intestazioni = dict(INTESTAZIONI)
    if gia:
        intestazioni["Range"] = "bytes=" + str(gia) + "-"
    req = urllib.request.Request(url, headers=intestazioni)
    with urllib.request.urlopen(req, timeout=60) as r:
        if gia and r.status != 206:  # il server non riprende: ricomincio
            gia = 0
            impronta = hashlib.sha256()
        lunghezza = r.headers.get("Content-Length")
        totale = grandezza or (gia + int(lunghezza) if lunghezza else None)
        scaricati = gia
        inizio = time.time()
        ultimo = 0
        with open(parziale, "ab" if gia else "wb") as f:
            while True:
                pezzo = r.read(1024 * 1024)
                if not pezzo:
                    break
                f.write(pezzo)
                if sha256:
                    impronta.update(pezzo)
                scaricati += len(pezzo)
                adesso = time.time()
                if adesso - ultimo > 0.5:
                    ultimo = adesso
                    velocita = (scaricati - gia) / max(adesso - inizio, 0.001)
                    testo = "\r      " + etichetta + ": " + dimensione(scaricati)
                    if totale:
                        mancano = (totale - scaricati) / velocita if velocita > 0 else 0
                        testo += " di " + dimensione(totale) + " (" + str(int(scaricati * 100 / totale)) + "%) - mancano " + durata(mancano)
                    testo += " - %.1f MB/s   " % (velocita / 1024 ** 2)
                    print(testo, end="", flush=True)
    print("\r" + " " * 100 + "\r", end="")
    if grandezza and scaricati != grandezza:
        raise ConnectionError("file incompleto (" + str(scaricati) + " su " + str(grandezza) + " byte)")
    if sha256 and impronta.hexdigest().lower() != sha256.lower():
        os.remove(parziale)
        raise RuntimeError("il file scaricato è rovinato (controllo sha256 fallito): riprova")
    ok(etichetta + ": scaricato (" + dimensione(scaricati) + ")")


# ================================================================ motore AI (llama.cpp)

def trova_motore(sistema):
    """Cerca l'ultima versione di llama.cpp per Windows o Linux.

    Attenzione: llama.cpp pubblica TUTTE le versioni come "pre-release", quindi non vanno scartate.
    """
    schema = MOTORI[sistema]["schema"]
    try:
        for versione in scarica_json(GITHUB_RELEASE_API):
            if versione.get("draft"):
                continue
            for a in versione.get("assets", []):
                if re.search(schema, a["name"]) and not a["name"].startswith("cudart") \
                        and a.get("state", "uploaded") == "uploaded":
                    digest = a.get("digest") or ""
                    return {"tag": versione["tag_name"], "nome": a["name"], "url": a["browser_download_url"],
                            "dimensione": a.get("size"),
                            "sha256": digest[7:] if digest.startswith("sha256:") else None}
        avviso("Nell'elenco di GitHub non c'è il file giusto, provo dalla pagina web...")
    except Exception as e:  # noqa: BLE001
        avviso("API di GitHub non disponibile (" + str(e) + "), provo dalla pagina web...")
    return trova_motore_dal_sito(sistema, schema)


def trova_motore_dal_sito(sistema, schema):
    """Piano B: legge le versioni dalle pagine web di GitHub (senza API)."""
    tag_trovati = []
    for pagina_web in (GITHUB_RELEASE_WEB, GITHUB_RELEASE_WEB.replace("/releases", "/tags")):
        try:
            pagina, _ = scarica_testo(pagina_web)
        except Exception:  # noqa: BLE001
            continue
        for tag in re.findall(r"/releases/tag/(b\d+)", pagina) + re.findall(r"/tree/(b\d+)", pagina):
            if tag not in tag_trovati:
                tag_trovati.append(tag)
        if tag_trovati:
            break
    tag_trovati.sort(key=lambda t: int(t[1:]), reverse=True)
    for tag in tag_trovati[:5]:
        try:
            pagina, _ = scarica_testo(GITHUB_RELEASE_WEB + "/expanded_assets/" + tag)
            for link in re.findall(r'href="([^"]+/releases/download/[^"]+)"', pagina):
                nome = link.split("/")[-1]
                if re.search(schema, nome) and not nome.startswith("cudart"):
                    return {"tag": tag, "nome": nome, "url": urllib.parse.urljoin(GITHUB_RELEASE_WEB, link),
                            "dimensione": None, "sha256": None}
        except Exception:  # noqa: BLE001
            pass
        # nome del file come lo crea llama.cpp: llama-<versione>-bin-win-cpu-x64.zip
        nome = "llama-" + tag + ("-bin-win-cpu-x64.zip" if sistema == "win" else "-bin-ubuntu-x64.tar.gz")
        url = GITHUB_RELEASE_WEB + "/download/" + tag + "/" + nome
        try:
            req = urllib.request.Request(url, headers=dict(INTESTAZIONI, Range="bytes=0-0"))
            with urllib.request.urlopen(req, timeout=60):
                return {"tag": tag, "nome": nome, "url": url, "dimensione": None, "sha256": None}
        except Exception:  # noqa: BLE001
            continue
    raise RuntimeError("non trovo il file di llama.cpp per " + sistema
                       + " (controlla che il PC riesca ad aprire github.com)")


def estrai_archivio(archivio, destinazione, eseguibile):
    """Estrae l'archivio e mette i file del motore direttamente in 'destinazione'."""
    temporanea = destinazione + "_estrazione"
    shutil.rmtree(temporanea, ignore_errors=True)
    os.makedirs(temporanea)
    if archivio.endswith(".zip"):
        with zipfile.ZipFile(archivio) as z:
            z.extractall(temporanea)
    else:
        estrai_tar(archivio, temporanea)
    sorgente = None
    for cartella, _, file in os.walk(temporanea):
        if eseguibile in file:
            sorgente = cartella
            break
    if not sorgente:
        raise RuntimeError("nell'archivio non c'è " + eseguibile)
    shutil.rmtree(destinazione, ignore_errors=True)
    shutil.move(sorgente, destinazione)
    shutil.rmtree(temporanea, ignore_errors=True)
    principale = os.path.join(destinazione, eseguibile)
    try:
        os.chmod(principale, 0o755)
    except OSError:
        pass


def estrai_tar(archivio, destinazione):
    """Come tar -xzf, ma i collegamenti diventano copie (la chiavetta FAT/exFAT non li supporta)."""
    collegamenti = []
    base = os.path.abspath(destinazione)
    with tarfile.open(archivio, "r:gz") as t:
        for m in t.getmembers():
            percorso = os.path.abspath(os.path.join(base, m.name))
            if not percorso.startswith(base + os.sep):
                continue
            if m.isdir():
                os.makedirs(percorso, exist_ok=True)
            elif m.isfile():
                os.makedirs(os.path.dirname(percorso), exist_ok=True)
                with t.extractfile(m) as sorgente, open(percorso, "wb") as f:
                    shutil.copyfileobj(sorgente, f)
                try:
                    os.chmod(percorso, 0o755 if m.mode & 0o111 else 0o644)
                except OSError:
                    pass
            elif m.issym() or m.islnk():
                obiettivo = m.linkname if m.islnk() else os.path.join(os.path.dirname(m.name), m.linkname)
                collegamenti.append((percorso, os.path.abspath(os.path.join(base, obiettivo))))
    for _ in range(3):  # anche collegamenti a collegamenti
        for percorso, obiettivo in collegamenti:
            if os.path.isfile(obiettivo) and not os.path.exists(percorso) and obiettivo.startswith(base + os.sep):
                shutil.copy2(obiettivo, percorso)


def prova_motore(cartella, eseguibile):
    """Restituisce (funziona, codice di uscita)."""
    percorso = os.path.join(cartella, eseguibile)
    ambiente = dict(os.environ)
    if not WINDOWS:
        ambiente["LD_LIBRARY_PATH"] = cartella + os.pathsep + ambiente.get("LD_LIBRARY_PATH", "")
    try:
        r = subprocess.run([percorso, "--version"], cwd=cartella, capture_output=True, timeout=120, env=ambiente)
        return r.returncode == 0, r.returncode
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def sistema_dll_windows(cartella):
    """Copia accanto al motore le librerie Visual C++ di questo PC, così funziona anche sui PC che non le hanno."""
    sistema32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    copiate = []
    for nome in DLL_VISUAL_CPP:
        sorgente = os.path.join(sistema32, nome)
        destinazione = os.path.join(cartella, nome)
        if os.path.isfile(sorgente) and not os.path.exists(destinazione):
            shutil.copy2(sorgente, destinazione)
            copiate.append(destinazione)
    funziona, codice = prova_motore(cartella, "llama-server.exe")
    if funziona:
        if copiate:
            ok("Librerie Visual C++ copiate sulla chiavetta (" + str(len(copiate)) + " file)")
        return True
    for f in copiate:  # con le copie non va: le tolgo e riprovo
        os.remove(f)
    funziona, codice = prova_motore(cartella, "llama-server.exe")
    if not funziona:
        errore("Il motore AI non parte su questo PC (codice " + str(codice) + ").")
        if codice in (3221225781, -1073741515):
            info("Mancano le librerie Visual C++: installa 'Microsoft Visual C++ Redistributable x64'")
            info("da https://aka.ms/vs/17/release/vc_redist.x64.exe e poi rilancia PREPARA_CHIAVETTA.")
    return funziona


def prepara_motore(sistema, aggiorna, installati):
    dati = MOTORI[sistema]
    principale = os.path.join(dati["cartella"], dati["eseguibile"])
    if os.path.isfile(principale) and not aggiorna:
        ok("Motore AI per " + sistema + ": già presente (" + str(installati.get(sistema, {}).get("tag", "?")) + ")")
        return True
    motore = trova_motore(sistema)
    archivio = os.path.join(SISTEMA, motore["nome"])
    scarica_file(motore["url"], archivio, motore["dimensione"], motore["sha256"],
                 "Motore AI " + sistema + " " + motore["tag"])
    estrai_archivio(archivio, dati["cartella"], dati["eseguibile"])
    os.remove(archivio)
    installati[sistema] = {"tag": motore["tag"], "file": motore["nome"]}
    if sistema == "win" and WINDOWS:
        return sistema_dll_windows(dati["cartella"])
    if sistema == "linux" and not WINDOWS:
        funziona, codice = prova_motore(dati["cartella"], dati["eseguibile"])
        if not funziona:
            errore("Il motore AI non parte su questo PC (codice " + str(codice) + ").")
        return funziona
    return True


# ================================================================ modelli

def file_del_repo(repo):
    for url in (HF + "/api/models/" + repo + "/tree/main", HF + "/api/models/" + repo + "?blobs=true"):
        try:
            dati = scarica_json(url)
        except urllib.error.HTTPError as e:
            if e.code in (401, 404):
                return []
            continue
        except Exception:  # noqa: BLE001
            continue
        elenco = []
        if isinstance(dati, list):
            for d in dati:
                if d.get("type") == "file":
                    lfs = d.get("lfs") or {}
                    elenco.append((d["path"], lfs.get("size") or d.get("size"), lfs.get("oid")))
        else:
            for s in dati.get("siblings", []):
                lfs = s.get("lfs") or {}
                elenco.append((s["rfilename"], s.get("size") or lfs.get("size"), lfs.get("sha256")))
        return elenco
    raise RuntimeError("Hugging Face non risponde")


def trova_modello(regola):
    quant = regola["quant"].lower()
    for repo in regola["repo"]:
        try:
            elenco = file_del_repo(repo)
        except RuntimeError:
            continue
        candidati = []
        for percorso, grandezza, sha in elenco:
            basso = percorso.lower()
            if (basso.endswith(".gguf") and quant in basso and "mmproj" not in basso
                    and not re.search(r"-\d{5}-of-\d{5}", basso)):
                esatto = basso.endswith("-" + quant + ".gguf") or basso.endswith("_" + quant + ".gguf")
                candidati.append((0 if esatto else 1, len(percorso), percorso, grandezza, sha))
        if candidati:
            _, _, percorso, grandezza, sha = sorted(candidati)[0]
            nome = regola["nome"] if repo == regola["repo"][0] else nome_da_file(percorso)
            return {"id": regola["id"], "nome": nome, "repo": repo, "file": os.path.basename(percorso),
                    "url": HF + "/" + repo + "/resolve/main/" + percorso, "dimensione": grandezza, "sha256": sha}
    return None


def nome_da_file(percorso):
    nome = os.path.basename(percorso)
    nome = re.sub(r"[-_.](?:ud-)?(?:i?q\d[\w]*|f16|bf16)\.gguf$", "", nome, flags=re.I)
    return nome.replace("Qwen_", "").replace("-Instruct", "").replace("-", " ")


# ================================================================ controlli sulla chiavetta

def tipo_filesystem(percorso):
    try:
        if WINDOWS:
            import ctypes
            radice = os.path.splitdrive(os.path.abspath(percorso))[0] + "\\"
            nome = ctypes.create_unicode_buffer(64)
            if ctypes.windll.kernel32.GetVolumeInformationW(radice, None, 0, None, None, None, nome, 64):
                return nome.value.upper()
            return ""
        assoluto = os.path.realpath(percorso)
        migliore, tipo = "", ""
        with open("/proc/mounts") as f:
            for r in f:
                parti = r.split()
                punto = parti[1].replace("\\040", " ")
                if (assoluto == punto or assoluto.startswith(punto.rstrip("/") + "/")) and len(punto) > len(migliore):
                    migliore, tipo = punto, parti[2].upper()
        return tipo
    except Exception:  # noqa: BLE001
        return ""


def chiedi(domanda, automatico):
    if automatico:
        return True
    try:
        return input(" " + domanda + " (S/n) ").strip().lower() in ("", "s", "si", "sì", "y", "yes")
    except EOFError:
        return True


# ================================================================ test finale

def test_finale():
    from assistente import ServerAI, modelli_installati, estrai_codice
    installati = modelli_installati()
    if not installati or not os.path.isfile(ESEGUIBILE_SERVER):
        return
    piu_piccolo = sorted(installati, key=lambda m: m.get("dimensione") or 0)[0]
    print()
    info("Test finale con il modello " + piu_piccolo.get("nome", piu_piccolo["file"]) + "...")
    server = ServerAI(piu_piccolo, 4096, carica_config())
    try:
        if not server.avvia():
            return
        risposta = server.richiesta_json("/v1/chat/completions", {
            "messages": [{"role": "user", "content": "Scrivi un programma Python che chiede due numeri e stampa la somma. Solo il codice."}],
            "max_tokens": 200, "temperature": 0.2, "chat_template_kwargs": {"enable_thinking": False}}, timeout=1800)
        testo = risposta["choices"][0]["message"].get("content") or ""
        print(C.DIM + estrai_codice(testo) + C.RESET)
        ok("Il test funziona!")
    except Exception as e:  # noqa: BLE001
        avviso("Test non riuscito: " + str(e))
    finally:
        server.ferma()


# ================================================================ programma principale

def main():
    abilita_colori()
    titolo_finestra("Preparazione chiavetta AI Python Offline")
    aggiorna = "--aggiorna" in sys.argv
    automatico = "--si" in sys.argv
    config = carica_config()
    installati = leggi_json(FILE_MODELLI, {}) or {}
    installati.setdefault("motori", {})
    for cartella in (CARTELLA_MODELLI, CARTELLA_PROGRAMMI, CARTELLA_DATI, CARTELLA_CACHE, CARTELLA_LOG):
        os.makedirs(cartella, exist_ok=True)

    print()
    riga("=")
    print(C.BOLD + C.CIANO + "   PREPARAZIONE DELLA CHIAVETTA" + C.RESET + "  (serve internet, solo la prima volta)")
    riga("=")

    filesystem = tipo_filesystem(RADICE)
    libero = shutil.disk_usage(RADICE).free
    info("Cartella: " + RADICE)
    info("Spazio libero: " + dimensione(libero) + ("   -  formato: " + filesystem if filesystem else ""))
    fat32 = filesystem in ("FAT32", "FAT", "VFAT", "MSDOS")
    if fat32:
        avviso("La chiavetta è in formato FAT32: non può contenere file più grandi di 4 GB.")
        info("Salto il modello grande. Per averlo: salva i file, formatta la chiavetta in exFAT e rifai.")

    # ---------------------------------------------------------- motori
    print()
    print(C.BOLD + " 1) Motore AI (llama.cpp)" + C.RESET)
    try:
        motore_ok = prepara_motore("win", aggiorna, installati["motori"])
    except Exception as e:  # noqa: BLE001
        errore("Non riesco a scaricare il motore per Windows: " + str(e))
        motore_ok = False
    try:
        prepara_motore("linux", aggiorna, installati["motori"])
    except Exception as e:  # noqa: BLE001
        avviso("Motore per Linux non scaricato (" + str(e) + "): servirà solo se usi Linux.")
    if not WINDOWS:
        motore_ok = os.path.isfile(os.path.join(CARTELLA_LLAMA_LINUX, "llama-server"))
    scrivi_json(FILE_MODELLI, installati)

    # ---------------------------------------------------------- modelli
    print()
    print(C.BOLD + " 2) Modelli AI (il 'cervello')" + C.RESET)
    da_scaricare = []
    presenti = {m["id"]: m for m in installati.get("modelli", [])}
    for regola in config["modelli"]:
        vecchio = presenti.get(regola["id"])
        if vecchio and os.path.isfile(os.path.join(CARTELLA_MODELLI, vecchio["file"])):
            ok("Modello " + regola["id"] + ": già presente (" + vecchio["nome"] + ")")
            continue
        modello = trova_modello(regola)
        if not modello:
            avviso("Non trovo online il modello " + regola["id"] + " (" + regola["nome"] + ")")
            continue
        if fat32 and (modello["dimensione"] or 0) >= 4 * 1024 ** 3:
            avviso("Salto " + modello["nome"] + ": troppo grande per FAT32")
            continue
        da_scaricare.append(modello)
        info("- " + modello["id"] + ": " + modello["nome"] + "  (" + dimensione(modello["dimensione"] or 0) + ")")

    totale = sum(m["dimensione"] or 0 for m in da_scaricare)
    if da_scaricare:
        info("Totale da scaricare: " + C.BOLD + dimensione(totale) + C.RESET)
        if totale > libero - 300 * 1024 ** 2:
            errore("Non c'è abbastanza spazio sulla chiavetta.")
            return 1
        if not chiedi("Scarico adesso? Con una connessione normale ci vogliono 10-40 minuti.", automatico):
            return 0
    for modello in da_scaricare:
        try:
            scarica_file(modello["url"], os.path.join(CARTELLA_MODELLI, modello["file"]), modello["dimensione"],
                         modello["sha256"], modello["nome"])
        except Exception as e:  # noqa: BLE001
            errore("Download di " + modello["nome"] + " non riuscito: " + str(e))
            continue
        voce = {k: modello[k] for k in ("id", "nome", "repo", "file", "dimensione", "sha256")}
        presenti[modello["id"]] = voce
        installati["modelli"] = [presenti[r["id"]] for r in config["modelli"] if r["id"] in presenti]
        scrivi_json(FILE_MODELLI, installati)

    # ---------------------------------------------------------- fine
    print()
    if not presenti:
        errore("Nessun modello scaricato: rilancia PREPARA_CHIAVETTA quando la connessione funziona.")
        return 1
    if motore_ok and "--senza-test" not in sys.argv:
        test_finale()
    print()
    riga("=")
    if motore_ok:
        ok(C.BOLD + "La chiavetta è pronta!" + C.RESET + " Su qualsiasi PC fai doppio clic su AVVIA_AI.bat")
    else:
        avviso("Modelli pronti, ma il motore AI ha dato problemi (vedi sopra).")
    riga("=")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print()
        avviso("Interrotto. Rilancia PREPARA_CHIAVETTA per continuare da dove eri arrivato.")
        sys.exit(1)
