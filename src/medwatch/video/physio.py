"""Análise de fisioterapia: ROM, assimetria, desvio de padrão e compensação de tronco."""
from dataclasses import dataclass, field

import numpy as np

from medwatch.video.dtw import dtw_distance, resample
from medwatch.video.geometry import angle_series, trunk_angle
from medwatch.video.models import Person
from medwatch.video.reps import segment_reps

MAX_PER_TYPE = 5
LOW_ROM_VS_MEDIAN = 0.7


@dataclass
class PhysioResult:
    """Repetições, achados e séries de ângulos de um vídeo de exercício."""

    reps: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    series: dict[str, list[float]] = field(default_factory=dict)


def _finding(type_, rep, t0, t1, score, payload, explanation) -> dict:
    return {
        "type": type_,
        "rep": rep,
        "t_start": float(t0),
        "t_end": float(t1),
        "score": float(min(1.0, max(0.0, score))),
        "payload": payload,
        "explanation": explanation,
    }


def _consolidate(per_rep: list[dict], n_reps: int) -> list[dict]:
    """>= 50% das repetições com o achado: uma evidência resumida; senão, uma por rep (máx. 5)."""
    if not per_rep:
        return []
    if len(per_rep) >= 0.5 * n_reps:
        first = per_rep[0]
        reps = [f["rep"] for f in per_rep]
        return [
            _finding(
                first["type"],
                None,
                min(f["t_start"] for f in per_rep),
                max(f["t_end"] for f in per_rep),
                max(f["score"] for f in per_rep),
                {**first["payload"], "reps": reps},
                f"{first['explanation']} (em {len(reps)} de {n_reps} repetições: {reps})",
            )
        ]
    return per_rep[:MAX_PER_TYPE]


def _low_rom(rep, rom_by_joint, ref_rom, median_rom, n_reps, ratio, t0, t1) -> dict | None:
    worst = None
    for joint, rom in rom_by_joint.items():
        if ref_rom:
            ref = ref_rom.get(joint, 0.0)
            below = ref > 0 and rom < ratio * ref
        else:
            ref = median_rom[joint]
            below = n_reps >= 3 and ref > 0 and rom < LOW_ROM_VS_MEDIAN * ref
        if not below:
            continue
        score = 1 - rom / ref
        if worst is None or score > worst[0]:
            worst = (score, joint, rom, ref)
    if worst is None:
        return None
    score, joint, rom, ref = worst
    what = "referência" if ref_rom else "mediana do vídeo"
    return _finding(
        "physio_low_rom", rep, t0, t1, score,
        {"joint": joint, "rom": rom, "reference_rom": ref},
        f"Rep. {rep}: amplitude de {joint} {rom:.0f}° ({what} {ref:.0f}°)",
    )


def analyze_physio(
    people_per_frame: list[Person | None],
    frame_times: list[float],
    fps: float,
    exercise_cfg: dict,
    reference: dict | None,
    thr: dict,
) -> PhysioResult:
    """Analisa a execução de um exercício; `thr` tem `keypoint_min_conf`."""
    cfg = exercise_cfg
    series = angle_series(people_per_frame, cfg["joints"], thr.get("keypoint_min_conf", 0.5))
    result = PhysioResult(series={k: [float(x) for x in v] for k, v in series.items()})
    primary = series[cfg["primary_joint"]]
    segs = segment_reps(primary, fps, cfg["rep_min_prominence_deg"], cfg["rep_min_distance_s"])
    if not segs:
        return result

    roms = [{j: float(np.ptp(s[a : b + 1])) for j, s in series.items()} for a, b in segs]
    ref_rom = (reference or {}).get("rom") or None
    median_rom = {j: float(np.median([r[j] for r in roms])) for j in series}

    low, asym, dev, trunk = [], [], [], []
    for i, (a, b) in enumerate(segs):
        n = i + 1
        t0, t1 = frame_times[a], frame_times[b]
        result.reps.append(
            {"rep": n, "start": a, "end": b, "t_start": t0, "t_end": t1, "rom": roms[i]}
        )

        f = _low_rom(n, roms[i], ref_rom, median_rom, len(segs), cfg["rom_min_ratio"], t0, t1)
        if f:
            low.append(f)

        worst_pair = None
        for left, right in cfg.get("pairs", []):
            diff = abs(roms[i][left] - roms[i][right])
            if diff > cfg["asymmetry_max_deg"] and (worst_pair is None or diff > worst_pair[0]):
                worst_pair = (diff, left, right)
        if worst_pair:
            diff, left, right = worst_pair
            asym.append(_finding(
                "physio_asymmetry", n, t0, t1, diff / 45,
                {"pair": [left, right], "diff_deg": diff},
                f"Rep. {n}: assimetria de {diff:.0f}° entre {left} e {right}",
            ))

        curves = (reference or {}).get("mean_curves", {})
        if cfg["primary_joint"] in curves:
            d = dtw_distance(
                resample(primary[a : b + 1], 50), np.asarray(curves[cfg["primary_joint"]])
            )
            if d > cfg["dtw_max"]:
                dev.append(_finding(
                    "physio_pattern_deviation", n, t0, t1, d / (2 * cfg["dtw_max"]),
                    {"dtw": d, "dtw_max": cfg["dtw_max"]},
                    f"Rep. {n}: padrão de movimento diverge da referência (DTW {d:.1f}°)",
                ))

        angles = [trunk_angle(p.keypoints) for p in people_per_frame[a : b + 1] if p is not None]
        if angles and max(angles) > cfg["trunk_max_deg"]:
            m = max(angles)
            trunk.append(_finding(
                "physio_trunk_compensation", n, t0, t1, m / 60,
                {"max_trunk_deg": m, "limit_deg": cfg["trunk_max_deg"]},
                f"Rep. {n}: inclinação do tronco de {m:.0f}° (limite {cfg['trunk_max_deg']}°)",
            ))

    for group in (low, asym, dev, trunk):
        result.findings.extend(_consolidate(group, len(segs)))
    return result
