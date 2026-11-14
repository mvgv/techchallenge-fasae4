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


def _detect_falls(hip_y, aspect, in_bed, times, fall_cfg, box_h=None) -> list[dict]:
    """Quedas: descida do quadril em `window_s`, seguida de fase deitada.

    Opções de `fall_cfg` (T41; o padrão reproduz a regra da T37):
    `drop_norm` "person" mede a descida em alturas da caixa no início da janela (e não do
    quadro); `lying_height_ratio` aceita como deitado uma caixa com altura ≤ essa fração da
    altura no início da janela (queda em direção à câmera); `skip_missing_j` usa o primeiro
    quadro com quadril até `LYING_GAP_S` depois do fim da janela; `end_closes_lying` dispensa
    `lying_min_s` quando a pessoa segue deitada ou sem pose até o fim do vídeo.
    """
    win, drop_min = fall_cfg["window_s"], fall_cfg["hip_drop_min"]
    lying_aspect, lying_min = fall_cfg["lying_aspect_min"], fall_cfg["lying_min_s"]
    by_person = fall_cfg.get("drop_norm", "frame") == "person"
    h_ratio = fall_cfg.get("lying_height_ratio")
    skip_j = fall_cfg.get("skip_missing_j", False)
    end_closes = fall_cfg.get("end_closes_lying", False)
    box_h = box_h if box_h is not None else [None] * len(times)
    out: list[dict] = []
    n = len(times)

    def lying(k: int, ref_h: float | None) -> bool:
        if aspect[k] is None or in_bed[k] is True:
            return False
        if aspect[k] >= lying_aspect:
            return True
        return bool(h_ratio and ref_h and box_h[k] is not None and box_h[k] <= h_ratio * ref_h)

    def drop_of(i: int, j: int) -> float | None:
        if hip_y[i] is None or hip_y[j] is None:
            return None
        d = hip_y[j] - hip_y[i]
        if by_person:
            return d / box_h[i] if box_h[i] else None
        return d

    i = 0
    while i < n:
        j = next((k for k in range(i + 1, n) if times[k] >= times[i] + win), None)
        if j is None:
            break
        if skip_j and hip_y[j] is None:
            j = next((k for k in range(j, n) if hip_y[k] is not None
                      and times[k] - times[i] - win <= LYING_GAP_S), j)
        ref_h = box_h[i]
        drop = drop_of(i, j)
        if drop is None or drop < drop_min or not lying(j, ref_h):
            i += 1
            continue
        end = k = j
        broke = False
        while k + 1 < n:
            k += 1
            if lying(k, ref_h):
                end = k
            elif aspect[k] is not None or times[k] - times[end] > LYING_GAP_S:
                broke = aspect[k] is not None
                break
        to_end = end_closes and not broke and not any(
            aspect[q] is not None and not lying(q, ref_h) for q in range(end + 1, n))
        if times[end] - times[j] < lying_min and not to_end:
            i += 1
            continue
        if to_end:
            end = n - 1
        out.append({
            "type": "fall_detected",
            "t_start": float(times[i]),
            "t_end": float(times[end]),
            "score": FALL_SCORE,
            "frame_index": int(j),
            "payload": {"t_video_s": float(times[j]), "hip_drop": float(drop)},
            "explanation": (
                f"Queda em {times[j]:.1f}s: quadril desceu {drop * 100:.0f}% da altura "
                f"{'da pessoa' if by_person else 'da imagem'} e a pessoa ficou deitada por "
                f"{times[end] - times[j]:.1f}s{' (até o fim do vídeo)' if to_end else ''}"
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

    box_h = [None if p is None else float(p.xyxy[3] - p.xyxy[1]) / height
             for p in people_per_frame]
    fall_hip_y = list(hip_y)
    if thr["fall"].get("hip_from_box", False):
        # sem os pontos do quadril, o centro da caixa faz o papel do quadril (T41)
        fall_hip_y = [
            hy if hy is not None or p is None else float(p.xyxy[1] + p.xyxy[3]) / 2 / height
            for hy, p in zip(hip_y, people_per_frame, strict=True)
        ]

    result = BedResult()
    result.findings += _detect_falls(fall_hip_y, aspect, in_bed, times, thr["fall"], box_h)
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
