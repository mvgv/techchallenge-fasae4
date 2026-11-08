"""Segmentação de repetições de exercício."""
import numpy as np
from scipy.signal import find_peaks


def _segment(primary: np.ndarray, distance: int, prominence: float) -> list[tuple[int, int]]:
    peaks, _ = find_peaks(primary, prominence=prominence, distance=distance)
    reps: list[tuple[int, int]] = []
    for s, e in zip(peaks[:-1], peaks[1:], strict=True):
        seg = primary[s : e + 1]
        depth = min(primary[s], primary[e]) - seg.min()
        if depth >= prominence:
            reps.append((int(s), int(e)))
    return reps


def segment_reps(
    primary: np.ndarray, fps: float, prominence: float, min_distance_s: float
) -> list[tuple[int, int]]:
    """Repetições como pares (início, fim) de topo a topo, cada uma com um vale >= prominence.

    Se houver menos de 2 topos, tenta a série invertida (exercícios como a abdução,
    em que o ângulo aumenta durante o movimento).
    """
    primary = np.asarray(primary, dtype=float)
    if len(primary) == 0 or np.isnan(primary).any():
        return []
    distance = max(1, int(min_distance_s * fps))
    peaks, _ = find_peaks(primary, prominence=prominence, distance=distance)
    if len(peaks) < 2:
        return _segment(-primary, distance, prominence)
    return _segment(primary, distance, prominence)
