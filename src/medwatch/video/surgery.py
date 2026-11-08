"""Análise de cirurgia: intrusão no campo estéril e controle de instrumentos."""
from dataclasses import dataclass, field

import numpy as np

from medwatch.video.geometry import point_in_zone
from medwatch.video.models import Detection, Person

INTRUSION_MIN_S = 3.0
INTRUSION_SCORE = 0.6
OUT_OF_ZONE_SCORE = 0.5
MISMATCH_SCORE = 0.8


@dataclass
class SurgeryResult:
    """Achados de um vídeo de cirurgia."""

    findings: list[dict] = field(default_factory=list)


def _center(xyxy) -> tuple[float, float]:
    return ((xyxy[0] + xyxy[2]) / 2, (xyxy[1] + xyxy[3]) / 2)


def _episodes(flags: list[bool], times: list[float], min_s: float) -> list[tuple[int, int]]:
    """Intervalos (índice inicial, final) de `flags` verdadeiros por ≥ `min_s` segundos."""
    out: list[tuple[int, int]] = []
    k, n = 0, len(flags)
    while k < n:
        if not flags[k]:
            k += 1
            continue
        e = k
        while e + 1 < n and flags[e + 1]:
            e += 1
        if times[e] - times[k] >= min_s:
            out.append((k, e))
        k = e + 1
    return out


def _intrusions(people, times, w, h, zone, max_people) -> list[dict]:
    flags = [
        sum(point_in_zone(_center(p.xyxy), zone, w, h) for p in ps) > max_people
        for ps in people
    ]
    return [
        {
            "type": "surgery_zone_intrusion",
            "t_start": float(times[a]),
            "t_end": float(times[b]),
            "score": INTRUSION_SCORE,
            "frame_index": int(a),
            "payload": {"t_video_s": float(times[a]), "max_people": int(max_people)},
            "explanation": (
                f"Mais de {max_people} pessoas no campo estéril por "
                f"{times[b] - times[a]:.1f}s a partir de {times[a]:.1f}s"
            ),
        }
        for a, b in _episodes(flags, times, INTRUSION_MIN_S)
    ]


def _instruments(dets: list[Detection], classes) -> list[Detection]:
    return [d for d in dets if d.cls in classes]


def _out_of_zone(dets, times, w, h, zones, classes, min_s) -> list[dict]:
    sterile, tray = zones["sterile_field"], zones["instrument_tray"]
    flags = []
    for ds in dets:
        flags.append(any(
            not point_in_zone(_center(d.xyxy), tray, w, h)
            and not point_in_zone(_center(d.xyxy), sterile, w, h)
            for d in _instruments(ds, classes)
        ))
    return [
        {
            "type": "surgery_instrument_out_of_zone",
            "t_start": float(times[a]),
            "t_end": float(times[b]),
            "score": OUT_OF_ZONE_SCORE,
            "frame_index": int(a),
            "payload": {"t_video_s": float(times[a])},
            "explanation": (
                f"Instrumento fora da bandeja e do campo estéril por "
                f"{times[b] - times[a]:.1f}s a partir de {times[a]:.1f}s"
            ),
        }
        for a, b in _episodes(flags, times, min_s)
    ]


def _count_mismatch(dets, times, w, h, zones, classes, window_s) -> list[dict]:
    if not times or times[-1] - times[0] < window_s:
        return []
    tray = zones["instrument_tray"]
    counts = [
        sum(point_in_zone(_center(d.xyxy), tray, w, h) for d in _instruments(ds, classes))
        for ds in dets
    ]
    first = [c for c, t in zip(counts, times, strict=True) if t < times[0] + window_s]
    last = [c for c, t in zip(counts, times, strict=True) if t > times[-1] - window_s]
    m0, m1 = float(np.median(first)), float(np.median(last))
    if m0 == m1:
        return []
    idx = next(k for k, t in enumerate(times) if t > times[-1] - window_s)
    return [{
        "type": "surgery_instrument_count_mismatch",
        "t_start": float(times[idx]),
        "t_end": float(times[-1]),
        "score": MISMATCH_SCORE,
        "severity": "critical",
        "frame_index": int(idx),
        "payload": {"count_start": m0, "count_end": m1, "t_video_s": float(times[idx])},
        "explanation": (
            f"Contagem de instrumentos na bandeja mudou de {m0:.0f} (início) para {m1:.0f} (fim)"
        ),
    }]


def analyze_surgery(
    dets_per_frame: list[list[Detection]],
    people_per_frame: list[list[Person]],
    frame_times: list[float],
    width: int,
    height: int,
    zones: dict,
    thr: dict,
) -> SurgeryResult:
    """Analisa intrusão, instrumentos fora de zona e contagem; `thr` é a seção `video`."""
    times = list(frame_times)
    classes = zones.get("instrument_classes", [])
    res = SurgeryResult()
    if "sterile_field" in zones:
        res.findings += _intrusions(
            people_per_frame, times, width, height,
            zones["sterile_field"], zones.get("max_people_sterile", 3),
        )
    if "sterile_field" in zones and "instrument_tray" in zones:
        res.findings += _out_of_zone(
            dets_per_frame, times, width, height, zones, classes, thr["instrument_out_min_s"]
        )
        res.findings += _count_mismatch(
            dets_per_frame, times, width, height, zones, classes, thr["count_window_s"]
        )
    res.findings.sort(key=lambda f: f["t_start"])
    return res
