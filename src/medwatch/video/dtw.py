"""Dynamic Time Warping entre séries de ângulos."""
import numpy as np


def dtw_distance(a: np.ndarray, b: np.ndarray) -> float:
    """DTW clássico; a e b com forma (n,) ou (n,k). Retorna custo / (n+m)."""
    a = a.reshape(len(a), -1)
    b = b.reshape(len(b), -1)
    n, m = len(a), len(b)
    D = np.full((n + 1, m + 1), np.inf)
    D[0, 0] = 0.0
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = float(np.linalg.norm(a[i - 1] - b[j - 1]))
            D[i, j] = cost + min(D[i - 1, j], D[i, j - 1], D[i - 1, j - 1])
    return float(D[n, m] / (n + m))


def resample(x: np.ndarray, n: int = 50) -> np.ndarray:
    """Reamostra linearmente para n pontos."""
    x = np.asarray(x, dtype=float)
    if len(x) == 1:
        return np.full(n, x[0])
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
