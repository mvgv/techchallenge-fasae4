"""Isolation Forest para sinais vitais: features, treino auxiliar e inferência."""
from __future__ import annotations

import json
import logging
from datetime import UTC
from pathlib import Path

import numpy as np

from medwatch.config import get_settings
from medwatch.contracts import VitalObservation

log = logging.getLogger(__name__)

CURRENT = ("hr", "sbp", "dbp", "spo2", "rr", "temp")
DELTAS = ("hr", "sbp", "spo2", "rr")
MODEL_NAME = "vitals_iforest"


def build_features(history: list[VitalObservation]) -> np.ndarray | None:
    """Monta as 10 features da última observação; None se faltar dado."""
    if len(history) < 6:
        return None
    last, prev = history[-1], history[-6:-1]
    cur = [getattr(last, k) for k in CURRENT]
    if any(v is None for v in cur):
        return None
    deltas = []
    for k in DELTAS:
        vals = [getattr(o, k) for o in prev if getattr(o, k) is not None]
        deltas.append(getattr(last, k) - float(np.mean(vals)) if vals else 0.0)
    return np.array([float(v) for v in cur] + deltas, dtype=float)


def normalize_score(s: float, p50: float, p01: float) -> float:
    """Score 0–1: 0 na mediana do treino, 1 em p01 ou abaixo."""
    den = p50 - p01
    if den <= 0:
        return 0.0
    return float(np.clip((p50 - s) / den, 0.0, 1.0))


class VitalsIForest:
    """Wrapper de inferência; desativado se o modelo não existir."""

    def __init__(self, models_dir: Path | None = None) -> None:
        self.dir = Path(models_dir) if models_dir else get_settings().models_dir
        self.pipeline = None
        self.meta: dict = {}
        self._warned = False

    @property
    def enabled(self) -> bool:
        """Indica se o modelo foi carregado."""
        return self.pipeline is not None

    def load(self) -> bool:
        """Carrega modelo e metadados; retorna False (com aviso único) se ausentes."""
        import joblib

        mp, jp = self.dir / f"{MODEL_NAME}.joblib", self.dir / f"{MODEL_NAME}.json"
        if not mp.exists() or not jp.exists():
            if not self._warned:
                log.warning("modelo %s não encontrado em %s; IForest desativado",
                            MODEL_NAME, self.dir)
                self._warned = True
            self.pipeline = None
            return False
        self.pipeline = joblib.load(mp)
        self.meta = json.loads(jp.read_text())
        return True

    def score(self, features: np.ndarray) -> tuple[bool, float]:
        """Retorna (é_anomalia, score normalizado 0–1)."""
        if self.pipeline is None:
            if not self._warned:
                log.warning("IForest desativado (modelo não carregado)")
                self._warned = True
            return False, 0.0
        x = np.asarray(features, dtype=float).reshape(1, -1)
        s = float(self.pipeline.score_samples(x)[0])
        return s < self.meta["threshold"], normalize_score(s, self.meta["p50"], self.meta["p01"])


def train_and_save(X: np.ndarray, models_dir: Path) -> dict:
    """Treina o pipeline, calcula limiares e salva .joblib e .json."""
    from datetime import datetime

    import joblib
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    pipe = Pipeline([("scaler", StandardScaler()),
                     ("iforest", IsolationForest(n_estimators=200, contamination="auto",
                                                 random_state=42))])
    pipe.fit(X)
    s = pipe.score_samples(X)
    meta = {"threshold": float(np.percentile(s, 0.5)), "p01": float(np.percentile(s, 1)),
            "p50": float(np.percentile(s, 50)),
            "trained_at": datetime.now(UTC).isoformat(), "n_samples": int(len(X))}
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, models_dir / f"{MODEL_NAME}.joblib")
    (models_dir / f"{MODEL_NAME}.json").write_text(json.dumps(meta, indent=2))
    return meta


def features_from_series(vitals: list[VitalObservation]) -> list[np.ndarray]:
    """Features de cada ponto de uma série ordenada."""
    out = []
    for i in range(5, len(vitals)):
        f = build_features(vitals[i - 5: i + 1])
        if f is not None:
            out.append(f)
    return out
