"""Análise de leito: queda, saída do leito e atividade por minuto."""
from dataclasses import dataclass, field

import numpy as np

from medwatch.video.geometry import point_in_zone
from medwatch.video.models import Person

HIP_IDX = (11, 12)
BED_MIN_S = 3.0
FALL_SCORE = 0.9
LYING_GAP_S = 1.5   # a pose costuma falhar com a pessoa deitada: lacunas até aqui não encerram a fase
BED_EXIT_SCORE = 0.5


@dataclass
class BedResult:
    """Achados e série de atividade por minuto de um vídeo de leito."""

    findings: list[dict] = field(default_factory=list)
    activity_per_minute: list[tuple[float, float, bool | None]] = field(default_factory=list)


def _hip(p: Person | None, min_conf: float) -> np.ndarray | None:
    if p is None or not all(p.kp_conf[i] >= min_conf for i in HIP_IDX):
        return None
    return np.mean([p.keypoints[i] for i in HIP_IDX], axis=0)


def _aspect(p: Person | None) -> float | None:
    if p is None:
        return None
    w, h = p.xyxy[2] - p.xyxy[0], p.xyxy[3] - p.xyxy[1]
    return float(w / h) if h > 0 else None


def _detect_falls(hip_y, aspect, in_bed, times, fall_cfg) -> list[dict]:
    win, drop_min = fall_cfg["window_s"], fall_cfg["hip_drop_min"]
    lying_aspect, lying_min = fall_cfg["lying_aspect_min"], fall_cfg["lying_min_s"]
    out: list[dict] = []
    n = len(times)

    def lying(k: int) -> bool:
        return aspect[k] is not None and aspect[k] >= lying_aspect and in_bed[k] is not True

    i = 0
    while i < n:
        j = next((k for k in range(i + 1, n) if times[k] >= times[i] + win), None)
        if j is None:
            break
        if (
            hip_y[i] is None
            or hip_y[j] is None
            or hip_y[j] - hip_y[i] < drop_min
            or not lying(j)
        ):
            i += 1
            continue
        end = k = j
        while k + 1 < n:
            k += 1
            if lying(k):
                end = k
            elif aspect[k] is not None or times[k] - times[end] > LYING_GAP_S:
                break
        if times[end] - times[j] < lying_min:
            i += 1
            continue
        drop = hip_y[j] - hip_y[i]
        out.append({
            "type": "fall_detected",
            "t_start": float(times[i]),
            "t_end": float(times[end]),
            "score": FALL_SCORE,
            "frame_index": int(j),
            "payload": {"t_video_s": float(times[j]), "hip_drop": float(drop)},
            "explanation": (
                f"Queda em {times[j]:.1f}s: quadril desceu {drop * 100:.0f}% da altura "
                f"e a pessoa ficou deitada por {times[end] - times[j]:.1f}s"
            ),
        })
        i = end + 1
    return out


def _runs(states) -> list[tuple[object, int, int]]:
    """Agrupa estados consecutivos iguais: (estado, índice inicial, índice final)."""
    runs: list[tuple[object, int, int]] = []
    for k, s in enumerate(states):
        if runs and runs[-1][0] == s:
            runs[-1] = (s, runs[-1][1], k)
        else:
            runs.append((s, k, k))
    return runs


def _detect_bed_exits(in_bed, times) -> list[dict]:
    out = []
    runs = _runs(in_bed)
    for r, nxt in zip(runs, runs[1:], strict=False):
        if r[0] is not True or nxt[0] is not False:
            continue
        if times[r[2]] - times[r[1]] < BED_MIN_S or times[nxt[2]] - times[nxt[1]] < BED_MIN_S:
            continue
        t = float(times[nxt[1]])
        out.append({
            "type": "bed_exit_video",
            "t_start": t,
            "t_end": float(times[nxt[2]]),
            "score": BED_EXIT_SCORE,
            "frame_index": int(nxt[1]),
            "payload": {"t_video_s": t},
            "explanation": f"Saída do leito em {t:.1f}s (≥ {BED_MIN_S:.0f}s dentro, depois fora)",
        })
    return out


def _motion(prev: Person | None, cur: Person | None, min_conf: float) -> float | None:
    if prev is None or cur is None:
        return None
    h = cur.xyxy[3] - cur.xyxy[1]
    ok = (prev.kp_conf >= min_conf) & (cur.kp_conf >= min_conf)
    if h <= 0 or not ok.any():
        return None
    d = np.linalg.norm(cur.keypoints[ok] - prev.keypoints[ok], axis=1)
    return float(d.mean() / h)


def analyze_bed(
    people_per_frame: list[Person | None],
    frame_times: list[float],
    width: int,
    height: int,
    zones: dict,
    thr: dict,
) -> BedResult:
    """Analisa queda, saída do leito e atividade; `thr` é a seção `video` dos limiares."""
    min_conf = thr.get("keypoint_min_conf", 0.5)
    bed = zones.get("bed")
    times = list(frame_times)
    hips = [_hip(p, min_conf) for p in people_per_frame]
    hip_y = [None if h is None else float(h[1]) / height for h in hips]
    aspect = [_aspect(p) for p in people_per_frame]
    in_bed = [
        None if h is None or bed is None else bool(point_in_zone(h, bed, width, height))
        for h in hips
    ]

    result = BedResult()
    result.findings += _detect_falls(hip_y, aspect, in_bed, times, thr["fall"])
    if bed:
        result.findings += _detect_bed_exits(in_bed, times)
    result.findings.sort(key=lambda f: f["t_start"])

    motion = [None] + [
        _motion(people_per_frame[k - 1], people_per_frame[k], min_conf)
        for k in range(1, len(times))
    ]
    if times:
        for m in range(int(times[-1] // 60) + 1):
            idx = [k for k, t in enumerate(times) if m * 60 <= t < (m + 1) * 60]
            vals = [motion[k] for k in idx if motion[k] is not None]
            mean = float(np.mean(vals)) if vals else 0.0
            act = float(np.clip(mean / thr["inactivity_motion_max"] * 10, 0, 100))
            seen = [in_bed[k] for k in idx if in_bed[k] is not None]
            flag = (sum(seen) > len(idx) / 2) if seen else None
            result.activity_per_minute.append((float(m * 60), act, flag))
    return result
