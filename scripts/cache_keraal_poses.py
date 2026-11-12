"""Roda o YOLOv8-pose nos vídeos do Keraal e guarda as poses (T40, passo 6).

Uso: python scripts/cache_keraal_poses.py [--fps 10] [--budget-s 520]
Grava data/datasets/keraal/poses/<video>.npz (t, kp, conf; NaN onde não há pessoa).
Retoma de onde parou. Dados clínicos (grupo 1A): nada disso vai para o Git.
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_rehab24_poses import run_video  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def video_paths(base: Path) -> list[Path]:
    """Vídeos das gravações anotadas (recs_*.csv), em ordem estável, sem repetir."""
    names: list[str] = []
    for recs in sorted(base.glob("recs_*.csv")):
        with open(recs, newline="", encoding="utf-8") as fh:
            names += [r["video"] for r in csv.DictReader(fh)]
    out = []
    for n in dict.fromkeys(names):
        g = "g1a" if n.startswith("G1A") else "g2a"
        out.append(base / g / "videos" / n)
    return out


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    from medwatch.video.models import PoseEstimator
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--weights", default=str(ROOT / "models" / "yolov8n-pose.pt"))
    ap.add_argument("--budget-s", type=float, default=520, help="para depois deste tempo")
    a = ap.parse_args(argv)
    base = a.data_dir / "datasets" / "keraal"
    (base / "poses").mkdir(exist_ok=True)
    videos = video_paths(base)
    t0 = time.time()
    for v in videos:
        out = base / "poses" / (v.stem + ".npz")
        if out.exists():
            continue
        if time.time() - t0 > a.budget_s:
            n = sum(1 for x in videos if (base / "poses" / (x.stem + ".npz")).exists())
            print(f"orçamento esgotado: {n}/{len(videos)} com pose; rode de novo")
            return
        pose = PoseEstimator(a.weights)  # um por vídeo: o tracking guarda estado
        res = run_video(v, pose, a.fps)
        np.savez_compressed(out.with_suffix(".tmp.npz"), **res)
        out.with_suffix(".tmp.npz").replace(out)
    print(f"todos os {len(videos)} vídeos têm pose")


if __name__ == "__main__":
    main()
