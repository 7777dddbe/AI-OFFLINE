#!/bin/sh
# Avvio su Linux:  apri un terminale nella chiavetta e scrivi:  sh AVVIA_AI_linux.sh
cd "$(dirname "$0")" || exit 1
CARTELLA="$(pwd)"
LLAMA="$CARTELLA/sistema/llama-linux"
if [ -f "$LLAMA/llama-server" ] && [ ! -x "$LLAMA/llama-server" ]; then
    # la chiavetta e' montata senza permesso di eseguire programmi: uso una copia temporanea (cancellata alla fine)
    COPIA="${XDG_RUNTIME_DIR:-/tmp}/ai-offline-llama-$$"
    mkdir -p "$COPIA" && cp -r "$LLAMA/." "$COPIA/" && chmod +x "$COPIA/llama-server"
    export AI_OFFLINE_LLAMA="$COPIA"
    trap 'rm -rf "$COPIA"' EXIT INT TERM
fi
python3 -B -E -s "$CARTELLA/sistema/app/assistente.py" "$@"
