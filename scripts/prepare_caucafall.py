"""Extrai o CAUCAFall e grava os rótulos por vídeo e por quadro (T41, passo A1).

Uso: python -I scripts/prepare_caucafall.py [--zip data/datasets/caucafall/caucafall_v4.zip]

Extrai só os AVI, os `.txt` YOLO e o `Dataset details.xlsx` (os 20 mil PNG são os mesmos
quadros do AVI). Alinhamento conferido casando PNG com quadros: o rótulo `<prefixo>NNNNN.txt`
corresponde ao quadro NNNNN-1 do AVI (base 0); rótulos além do fim do AVI são descartados
(quase todo vídeo tem um a mais; `Subject.6/Fall backwards` tem 23). Três `.txt` com sufixo
de letra (`...a.txt`, `...w.txt`) são duplicatas e ficam de fora.

Saídas em data/datasets/caucafall/: `videos.csv` (um vídeo por linha, intervalo dos quadros
rotulados como queda = corpo no chão) e `frames.csv` (classe e caixa YOLO por quadro).
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CF = ROOT / "data" / "datasets" / "caucafall"
INNER = "Dataset CAUCAFall/CAUCAFall"
LABEL_RE = re.compile(r"(\d{5})\.txt$")
VIDEO_COLUMNS = ["seq", "subject", "activity", "is_fall", "avi", "n_frames", "fps",
                 "fall_first", "fall_last"]
FRAME_COLUMNS = ["seq", "frame", "cls", "cx", "cy", "w", "h"]


def seq_name(subject: int, activity: str) -> str:
    """Nome curto da sequência: `s01-fall-backwards`, `s10-pick-up-object`."""
    return f"s{subject:02d}-" + re.sub(r"[^a-z0-9]+", "-", activity.lower()).strip("-")


def label_frame(filename: str) -> int | None:
    """Quadro do AVI (base 0) de um arquivo de rótulo; None para `classes.txt` e duplicatas."""
    m = LABEL_RE.search(filename)
    return int(m.group(1)) - 1 if m else None


def parse_label(text: str) -> tuple[int, float, float, float, float] | None:
    """Primeira linha YOLO (classe, cx, cy, w, h normalizados); None se vazio."""
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            return int(parts[0]), *(float(x) for x in parts[1:5])
    return None


def frame_labels(files: dict[str, str], n_frames: int) -> dict[int, tuple]:
    """Rótulos por quadro a partir de {nome: conteúdo}, descartando o que passa do AVI."""
    out = {}
    for name, text in files.items():
        k = label_frame(name)
        lab = parse_label(text) if k is not None else None
        if lab is not None and 0 <= k < n_frames:
            out[k] = lab
    return out


def fall_span(labels: dict[int, tuple]) -> tuple[int, int] | None:
    """Primeiro e último quadro com classe 1 (queda: corpo no chão)."""
    ones = [k for k, v in labels.items() if v[0] == 1]
    return (min(ones), max(ones)) if ones else None


def _avi_info(path: Path) -> tuple[int, float]:
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS)) or 20.0
    n = 0
    while cap.grab():
        n += 1
    cap.release()
    return n, fps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zip", type=Path, default=CF / "caucafall_v4.zip")
    ap.add_argument("--out", type=Path, default=CF)
    a = ap.parse_args()
    raw = a.out / "raw"
    z = zipfile.ZipFile(a.zip)
    by_dir: dict[str, dict[str, zipfile.ZipInfo]] = {}
    for info in z.infolist():
        if info.filename.endswith((".avi", ".txt", ".xlsx")):
            target = raw / info.filename
            if not target.exists() or target.stat().st_size != info.file_size:
                z.extract(info, raw)
        parts = info.filename.split("/")
        if len(parts) == 5 and info.filename.startswith(INNER + "/"):
            by_dir.setdefault("/".join(parts[2:4]), {})[parts[4]] = info

    videos, frames = [], []
    for folder in sorted(by_dir, key=lambda f: (int(f.split("/")[0].split(".")[1]), f)):
        subj_s, activity = folder.split("/")
        subject = int(subj_s.split(".")[1])
        files = by_dir[folder]
        avi = next(n for n in files if n.endswith(".avi"))
        n_frames, fps = _avi_info(raw / INNER / folder / avi)
        texts = {n: z.read(i).decode("utf-8", "replace") for n, i in files.items()
                 if n.endswith(".txt")}
        labels = frame_labels(texts, n_frames)
        span = fall_span(labels)
        seq = seq_name(subject, activity)
        videos.append({
            "seq": seq, "subject": subject, "activity": activity,
            "is_fall": int(activity.startswith("Fall")),
            "avi": f"raw/{INNER}/{folder}/{avi}", "n_frames": n_frames, "fps": f"{fps:g}",
            "fall_first": "" if span is None else span[0],
            "fall_last": "" if span is None else span[1],
        })
        for k in sorted(labels):
            c, cx, cy, w, h = labels[k]
            frames.append({"seq": seq, "frame": k, "cls": c, "cx": cx, "cy": cy, "w": w, "h": h})

    for name, cols, rows in (("videos.csv", VIDEO_COLUMNS, videos),
                             ("frames.csv", FRAME_COLUMNS, frames)):
        with open(a.out / name, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=cols)
            wr.writeheader()
            wr.writerows(rows)
    n_fall = sum(v["is_fall"] for v in videos)
    mism = [v["seq"] for v in videos if bool(v["is_fall"]) != (v["fall_first"] != "")]
    print(f"{len(videos)} vídeos ({n_fall} quedas), {len(frames)} quadros rotulados; "
          f"queda sem rótulo 1 ou ADL com rótulo 1: {mism or 'nenhum'}")


if __name__ == "__main__":
    main()
