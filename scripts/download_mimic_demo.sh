#!/usr/bin/env bash
# Baixa o MIMIC-IV Demo (acesso aberto, sem credenciamento) e prepara os parquets.
set -euo pipefail
wget -r -N -c -np https://physionet.org/files/mimic-iv-demo/2.2/ -P data/mimic
python scripts/prepare_mimic.py data/mimic
