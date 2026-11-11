"""Roda o YOLOv8-pose nos vídeos de agachamento do REHAB24-6 e guarda as poses (T39, passo 4).

Uso: python scripts/cache_rehab24_poses.py [--splits calibracao validacao reservado] [--fps 10]
Grava data/datasets/rehab24/poses/<video>.npz (t, kp, conf; NaN onde não há pessoa).
Retoma de onde parou (pula vídeos já gravados). Nada disso vai para o Git.
"""
import argparse
import csv
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run_video(video: Path, pose, fps: int, max_side: int = 960) -> dict:
    """Pose da pessoa principal a `fps` quadros/s; devolve t (N), kp (N,17,2) e conf (N,17)."""
    import cv2

    from medwatch.video.frames import iter_frames
    from medwatch.video.models import main_person

    ts, kps, confs = [], [], []
    for f in iter_frames(video, fps):
        img = f.image
        scale = max_side / max(img.shape[:2])
        if scale < 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        p = main_person(pose(img)[0])
        ts.append(f.t)
        if p is None:
            kps.append(np.full((17, 2), np.nan))
            confs.append(np.zeros(17))
        else:
            kps.append(p.keypoints / (scale if scale < 1 else 1.0))
            confs.append(p.kp_conf)
    return {"t": np.array(ts), "kp": np.array(kps), "conf": np.array(confs)}


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    from medwatch.video.models import PoseEstimator
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    ap.add_argument("--splits", nargs="+", default=["calibracao", "validacao", "reservado"])
    ap.add_argument("--cameras", nargs="+", type=int, default=[17, 18])
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--weights", default=str(ROOT / "models" / "yolov8n-pose.pt"))
    ap.add_argument("--budget-s", type=float, default=520, help="para depois deste tempo")
    a = ap.parse_args(argv)
    base = a.data_dir / "datasets" / "rehab24"
    with open(base / "reps.csv", newline="", encoding="utf-8") as fh:
        videos = list(dict.fromkeys(
            r["video"] for r in csv.DictReader(fh)
            if r["split"] in a.splits and int(r["camera"]) in a.cameras))
    (base / "poses").mkdir(exist_ok=True)
    t0 = time.time()
    for v in videos:
        out = base / "poses" / (Path(v).stem + ".npz")
        if out.exists():
            continue
        if time.time() - t0 > a.budget_s:
            print("orçamento de tempo esgotado; rode de novo para continuar")
            return
        pose = PoseEstimator(a.weights)  # um por vídeo: o tracking guarda estado
        res = run_video(base / "squat" / v, pose, a.fps)
        np.savez_compressed(out.with_suffix(".tmp.npz"), **res)
        out.with_suffix(".tmp.npz").replace(out)
        print(f"ok {v}: {len(res['t'])} quadros em {time.time() - t0:.0f} s")
    print("todos os vídeos têm pose")


if __name__ == "__main__":
    main()
