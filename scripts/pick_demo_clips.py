"""Escolhe e copia os clipes reservados para a demonstração (T37, passo 11).

Áudio: o clipe reservado de cada classe (tosse, respiração, ronco) em que o AST dá o maior score
ao rótulo esperado; UR Fall: a queda reservada fall-12 (uma das duas detectadas pela regra calibrada).
Copia para data/samples/ (fora do Git) e imprime a escolha para registrar em docs/DATASETS.md.
Uso: python scripts/pick_demo_clips.py
"""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ESC = ROOT / "data" / "datasets" / "esc50"
OUT = ROOT / "data" / "samples"
LABEL = {"coughing": ("Cough", "cough"), "breathing": ("Gasp", "breathing"),
         "snoring": ("Snoring", "snoring")}


def main() -> None:
    splits = yaml.safe_load((ROOT / "config" / "splits.yaml").read_text(encoding="utf-8"))
    preds = json.loads((ESC / "ast_predictions.json").read_text())
    with open(ESC / "meta" / "esc50.csv", newline="", encoding="utf-8") as fh:
        meta = {r["filename"]: r for r in csv.DictReader(fh)}
    OUT.mkdir(parents=True, exist_ok=True)
    for cls, (label, name) in LABEL.items():
        cands = [(max((p["score"] for p in preds[f] if p["label"] == label), default=0.0), f)
                 for f in splits["audio"]["reservado"] if meta[f]["category"] == cls]
        score, fname = max(cands)
        shutil.copy(ESC / "audio" / fname, OUT / f"{name}.wav")
        print(f"{name}.wav <- {fname} ({label} {score:.2f})")
    fall = ROOT / "data" / "datasets" / "urfall" / "video" / "fall-12.mp4"
    shutil.copy(fall, OUT / "bed_fall.mp4")
    print("bed_fall.mp4 <- fall-12.mp4 (queda reservada)")


if __name__ == "__main__":
    main()
