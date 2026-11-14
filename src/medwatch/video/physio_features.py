"""Medidas por repetição (ou gravação) para os modelos de fisioterapia com aprendizado (T41)."""
from __future__ import annotations

import numpy as np

from medwatch.video.dtw import dtw_distance, resample
from medwatch.video.geometry import angle_series, trunk_angle
from medwatch.video.models import Person
from medwatch.video.reps import segment_reps

CURVE_POINTS = 20
EDGE_PAD = 2   # metade da janela do filtro de mediana de angle_series
DTW_POINTS = 50
SHOULDERS, HIPS = (5, 6), (11, 12)
ELBOWS = {"elbow_left": [5, 7, 9], "elbow_right": [6, 8, 10]}


def _nanptp(x: np.ndarray) -> float:
    return float(np.nanmax(x) - np.nanmin(x)) if np.isfinite(x).any() else float("nan")


def _width_ratio(p: Person, min_conf: float) -> float | None:
    idx = (*SHOULDERS, *HIPS)
    if any(p.kp_conf[i] < min_conf for i in idx):
        return None
    sh = abs(p.keypoints[SHOULDERS[0]][0] - p.keypoints[SHOULDERS[1]][0])
    hp = abs(p.keypoints[HIPS[0]][0] - p.keypoints[HIPS[1]][0])
    return float(sh / hp) if hp > 1e-6 else None


def _trunk(p: Person, min_conf: float) -> float | None:
    if any(p.kp_conf[i] < min_conf for i in (*SHOULDERS, *HIPS)):
        return None
    return trunk_angle(p.keypoints)


def _series(people: list[Person | None], joints: dict, min_conf: float) -> dict[str, np.ndarray]:
    """`angle_series` sem o efeito de borda do filtro de mediana (que completa com zeros)."""
    pad = EDGE_PAD
    s = angle_series([people[0]] * pad + list(people) + [people[-1]] * pad, joints, min_conf)
    return {k: v[pad:-pad] for k, v in s.items()}


def joint_series(people: list[Person | None], cfg: dict, min_conf: float = 0.5
                 ) -> dict[str, np.ndarray]:
    """Séries de ângulos das articulações do exercício (para recalcular só o DTW)."""
    return _series(people, cfg["joints"], min_conf)


def dtw_features(series: dict[str, np.ndarray], reference: dict | None) -> dict[str, float]:
    """DTW de cada articulação para a curva média da referência (NaN sem referência)."""
    curves = (reference or {}).get("mean_curves", {})
    out = {f"dtw_{j}": float("nan") for j in series}
    for j, s in series.items():
        if j in curves and len(s) and np.isfinite(s).all():
            out[f"dtw_{j}"] = dtw_distance(resample(s, DTW_POINTS), np.asarray(curves[j]))
    return out


def feature_names(cfg: dict, reference: dict | None = None) -> list[str]:
    """Nomes das medidas, na ordem de `feature_vector`, para um exercício."""
    joints = list(cfg["joints"])
    names = [f"rom_{j}" for j in joints]
    names += [f"asym_{a}_{b}" for a, b in cfg.get("pairs", [])]
    names += [f"dtw_{j}" for j in joints]
    names += ["trunk_max", "trunk_min", "width_ratio_min", "width_ratio_max", "elbow_min",
              "duration_s", "n_reps", "missing_frac"]
    names += [f"curve_{k:02d}" for k in range(CURVE_POINTS)]
    return names


def feature_vector(
    people: list[Person | None],
    times: list[float],
    cfg: dict,
    reference: dict | None = None,
    min_conf: float = 0.5,
    fps: float | None = None,
) -> dict[str, float]:
    """Vetor fixo de medidas de uma repetição ou gravação (NaN onde falta pose).

    Amplitude e DTW (para a curva média da referência) por articulação, assimetria por par,
    inclinação do tronco máxima e mínima, razão entre larguras dos ombros e dos quadris
    (mínima e máxima: rotação vista de frente), menor ângulo do cotovelo, duração, número de
    repetições detectadas, fração de quadros sem pose e a curva da articulação principal
    reamostrada em `CURVE_POINTS` pontos.
    """
    out = dict.fromkeys(feature_names(cfg, reference), float("nan"))
    n = len(people)
    seen = [p for p in people if p is not None]
    prim_idx = cfg["joints"][cfg["primary_joint"]]
    ok = [p is not None and min(p.kp_conf[i] for i in prim_idx) >= min_conf for p in people]
    out["missing_frac"] = 1.0 - (sum(ok) / n) if n else 1.0
    out["duration_s"] = float(times[-1] - times[0]) if len(times) > 1 else 0.0
    if not any(ok):
        return out
    series = _series(people, cfg["joints"], min_conf)
    for j, s in series.items():
        out[f"rom_{j}"] = _nanptp(s)
    for a, b in cfg.get("pairs", []):
        out[f"asym_{a}_{b}"] = abs(out[f"rom_{a}"] - out[f"rom_{b}"])
    out.update(dtw_features(series, reference))
    trunk =[t for t in (_trunk(p, min_conf) for p in seen) if t is not None]
    if trunk:
        out["trunk_max"], out["trunk_min"] = float(max(trunk)), float(min(trunk))
    ratio = [r for r in (_width_ratio(p, min_conf) for p in seen) if r is not None]
    if ratio:
        out["width_ratio_min"], out["width_ratio_max"] = float(min(ratio)), float(max(ratio))
    elbows = _series(people, ELBOWS, min_conf)
    vals = np.concatenate([e[np.isfinite(e)] for e in elbows.values()])
    if vals.size:
        out["elbow_min"] = float(vals.min())
    prim = series[cfg["primary_joint"]]
    if np.isfinite(prim).all():
        for k, v in enumerate(resample(prim, CURVE_POINTS)):
            out[f"curve_{k:02d}"] = float(v)
        f = fps or (1.0 / float(np.median(np.diff(times))) if len(times) > 2 else 10.0)
        out["n_reps"] = float(len(segment_reps(prim, f, cfg["rep_min_prominence_deg"],
                                               cfg["rep_min_distance_s"])))
    return out


def to_matrix(rows: list[dict[str, float]], names: list[str]) -> np.ndarray:
    """Matriz (amostras × medidas) na ordem de `names`."""
    return np.array([[r.get(k, np.nan) for k in names] for r in rows], dtype=float)
