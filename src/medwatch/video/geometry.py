"""Geometria de keypoints: ângulos articulares, tronco e zonas."""
import cv2
import numpy as np
import pandas as pd
from scipy.signal import medfilt

from medwatch.video.models import Person


def joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Ângulo em b (graus) formado por a-b-c."""
    ba, bc = a - b, c - b
    cos = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-9)
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


def trunk_angle(kp: np.ndarray) -> float:
    """Inclinação do tronco em relação à vertical (ombros 5,6 vs. quadris 11,12)."""
    sh, hp = (kp[5] + kp[6]) / 2, (kp[11] + kp[12]) / 2
    v = sh - hp
    return float(np.degrees(np.arctan2(abs(v[0]), abs(v[1]) + 1e-9)))


def angle_series(
    people_per_frame: list[Person | None],
    joints: dict[str, list[int]],
    min_conf: float,
) -> dict[str, np.ndarray]:
    """Uma série por articulação; NaN (baixa confiança) é interpolado e a série suavizada."""
    out: dict[str, np.ndarray] = {}
    for name, (ia, ib, ic) in joints.items():
        vals = np.full(len(people_per_frame), np.nan)
        for i, p in enumerate(people_per_frame):
            if p is None:
                continue
            if min(p.kp_conf[ia], p.kp_conf[ib], p.kp_conf[ic]) < min_conf:
                continue
            vals[i] = joint_angle(p.keypoints[ia], p.keypoints[ib], p.keypoints[ic])
        if np.isnan(vals).all():
            out[name] = vals
            continue
        s = pd.Series(vals).interpolate(limit_direction="both").to_numpy()
        out[name] = medfilt(s, kernel_size=5)
    return out


def point_in_zone(pt_xy, polygon_norm, width: int, height: int) -> bool:
    """True se o ponto (pixels) está dentro do polígono normalizado (0–1)."""
    poly = np.array(
        [[x * width, y * height] for x, y in polygon_norm], dtype=np.float32
    ).reshape(-1, 1, 2)
    return cv2.pointPolygonTest(poly, (float(pt_xy[0]), float(pt_xy[1])), False) >= 0
