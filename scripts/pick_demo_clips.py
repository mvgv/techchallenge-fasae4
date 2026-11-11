"""Escolhe e copia os clipes reservados para a demonstração (T37, passo 11).

Áudio: o clipe reservado de cada classe (tosse, respiração, ronco) em que o AST dá o maior score
ao rótulo esperado; UR Fall: a queda reservada fall-12 (uma das duas detectadas pela regra calibrada).
Fisioterapia (T39): do REHAB24-6, só voluntários reservados e câmera 18, uma janela de ~30 s com
o maior peso de repetições incorretas (`physio_squat_wrong.mp4`) e uma só de corretas
(`physio_squat_correct.mp4`, controle). Copia para data/samples/ (fora do Git) e imprime
a escolha para registrar em docs/DATASETS.md.
Uso: python scripts/pick_demo_clips.py
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ESC = ROOT / "data" / "datasets" / "esc50"
OUT = ROOT / "data" / "samples"
LABEL = {"coughing": ("Cough", "cough"), "breathing": ("Gasp", "breathing"),
         "snoring": ("Snoring", "snoring")}


def pick_windows(reps: list[dict], length_s: float = 30.0, min_reps: int = 5) -> dict:
    """Janelas de `length_s` s a partir de cada repetição; devolve a mais incorreta e a mais correta.

    `reps`: dicts com video, rep_start_s, rep_end_s, label (de um só voluntário e câmera).
    Cada janela é (video, início, fim, n_reps, n_incorretas); só conta repetições inteiras dentro.
    """
    cands = []
    for r in reps:
        t0 = r["rep_start_s"]
        inside = [x for x in reps if x["video"] == r["video"] and x["rep_start_s"] >= t0
                  and x["rep_end_s"] <= t0 + length_s]
        if len(inside) >= min_reps:
            end = max(x["rep_end_s"] for x in inside)
            cands.append((r["video"], t0, end, len(inside),
                          sum(x["label"] == "incorrect" for x in inside)))
    if not cands:
        raise ValueError("nenhuma janela com repetições suficientes")
    wrong = max(cands, key=lambda c: (c[4] / c[3], c[3]))
    right = max((c for c in cands if c[4] == 0), key=lambda c: c[3], default=None)
    return {"wrong": wrong, "correct": right}


def cut_clip(src: Path, dest: Path, start: float, end: float) -> None:
    """Recorta [start, end] do vídeo (H.264, sem áudio, lado maior de 1280 px)."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, start - 1):.2f}", "-i", str(src),
         "-t", f"{end - start + 2:.2f}", "-an", "-vf", "scale=-2:1280", "-c:v", "libx264",
         "-pix_fmt", "yuv420p", str(dest)], check=True)


def pick_physio(out: Path) -> None:
    """Grava os dois clipes de fisioterapia a partir de voluntários reservados."""
    base = ROOT / "data" / "datasets" / "rehab24"
    with open(base / "reps.csv", newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["split"] == "reservado" and r["camera"] == "18"]
    for r in rows:
        r["rep_start_s"], r["rep_end_s"] = float(r["rep_start_s"]), float(r["rep_end_s"])
    best: dict = {"wrong": None, "correct": None}
    for subject in sorted({r["subject"] for r in rows}):
        w = pick_windows([r for r in rows if r["subject"] == subject])
        if best["wrong"] is None or w["wrong"][4] / w["wrong"][3] > best["wrong"][4] / best["wrong"][3]:
            best["wrong"] = (*w["wrong"], subject)
        if w["correct"] and (best["correct"] is None or w["correct"][3] > best["correct"][3]):
            best["correct"] = (*w["correct"], subject)
    for kind, name in (("wrong", "physio_squat_wrong.mp4"), ("correct", "physio_squat_correct.mp4")):
        video, a, b, n, n_inc, subject = best[kind]
        cut_clip(base / "squat" / video, out / name, a, b)
        print(f"{name} <- {video} {a:.1f}-{b:.1f} s, voluntário {subject}: "
              f"{n} repetições, {n_inc} incorretas")


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
    pick_physio(OUT)


if __name__ == "__main__":
    main()
