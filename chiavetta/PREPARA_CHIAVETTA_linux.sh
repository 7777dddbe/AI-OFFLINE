#!/bin/sh
# Preparazione su Linux (serve internet):  sh PREPARA_CHIAVETTA_linux.sh
cd "$(dirname "$0")" || exit 1
python3 -B -E -s "$(pwd)/sistema/app/prepara.py" "$@"
