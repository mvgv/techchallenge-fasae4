"""Gera data/references/<exercise>.json a partir de um vídeo de execução correta."""
import argparse
import json
from pathlib import Path

import numpy as np
import yaml

from medwatch.video.dtw import resample
from medwatch.video.frames import iter_frames
from medwatch.video.geometry import angle_series
from medwatch.video.models import PoseEstimator, main_person
from medwatch.video.reps import segment_reps


def build_reference(exercise: str, cfg: dict, series: dict[str, np.ndarray], fps: float) -> dict:
    """Monta a referência a partir das séries de ângulos."""
    reps = segment_reps(
        series[cfg["primary_joint"]],
        fps,
        cfg["rep_min_prominence_deg"],
        cfg["rep_min_distance_s"],
    )
    if not reps:
        raise ValueError("Nenhuma repetição encontrada no vídeo")
    mean_curves: dict[str, list[float]] = {}
    rom: dict[str, float] = {}
    for joint, s in series.items():
        curves = np.array([resample(s[a : b + 1], 50) for a, b in reps])
        mean_curves[joint] = curves.mean(axis=0).tolist()
        rom[joint] = float(np.mean([c.max() - c.min() for c in curves]))
    return {
        "exercise": exercise,
        "fps": fps,
        "n_reps": len(reps),
        "mean_curves": mean_curves,
        "rom": rom,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--exercise", required=True)
    ap.add_argument("--config", default="config/exercises.yaml")
    ap.add_argument("--weights", default="models/yolov8n-pose.pt")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--min-conf", type=float, default=0.5)
    ap.add_argument("--output-dir", default="data/references")
    args = ap.parse_args()
    cfg = yaml.safe_load(Path(args.config).read_text())[args.exercise]
    pose = PoseEstimator(args.weights)
    people = [main_person(pose(f.image)[0]) for f in iter_frames(Path(args.video), args.fps)]
    series = angle_series(people, cfg["joints"], args.min_conf)
    ref = build_reference(args.exercise, cfg, series, float(args.fps))
    out = Path(args.output_dir) / f"{args.exercise}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ref, indent=2))
    print(f"{ref['n_reps']} repetições -> {out}")


if __name__ == "__main__":
    main()
