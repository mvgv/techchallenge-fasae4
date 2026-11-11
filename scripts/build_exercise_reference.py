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


def reference_from_intervals(
    exercise: str,
    series_list: list[dict[str, np.ndarray]],
    intervals: list[list[tuple[int, int]]],
    fps: float,
) -> dict:
    """Referência de vários vídeos: `intervals[i]` são as repetições (índices) de `series_list[i]`."""
    curves: dict[str, list[np.ndarray]] = {}
    for series, reps in zip(series_list, intervals, strict=True):
        for a, b in reps:
            for joint, s in series.items():
                curves.setdefault(joint, []).append(resample(s[a : b + 1], 50))
    n_reps = len(next(iter(curves.values()), []))
    if n_reps == 0:
        raise ValueError("Nenhuma repetição para montar a referência")
    return {
        "exercise": exercise,
        "fps": fps,
        "n_reps": n_reps,
        "mean_curves": {j: np.mean(c, axis=0).tolist() for j, c in curves.items()},
        "rom": {j: float(np.mean([c.max() - c.min() for c in cs])) for j, cs in curves.items()},
    }


def build_reference(exercise: str, cfg: dict, series: dict[str, np.ndarray], fps: float) -> dict:
    """Monta a referência a partir das séries de ângulos de um vídeo (repetições detectadas)."""
    reps = segment_reps(
        series[cfg["primary_joint"]],
        fps,
        cfg["rep_min_prominence_deg"],
        cfg["rep_min_distance_s"],
    )
    if not reps:
        raise ValueError("Nenhuma repetição encontrada no vídeo")
    return reference_from_intervals(exercise, [series], [reps], fps)


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
