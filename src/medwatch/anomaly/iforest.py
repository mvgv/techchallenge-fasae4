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


def build_features(history: list[VitalObservation],
                   carry_forward: bool = False) -> np.ndarray | None:
    """Monta as 10 features da última observação; None se faltar dado.

    Com `carry_forward`, um sinal ausente na última observação usa o último valor
    conhecido nas 5 anteriores (dados reais medem a temperatura a cada ~4 h).
    """
    if len(history) < 6:
        return None
    last, prev = history[-1], history[-6:-1]
    cur = [getattr(last, k) for k in CURRENT]
    if carry_forward:
        for i, k in enumerate(CURRENT):
            if cur[i] is None:
                cur[i] = next((getattr(o, k) for o in reversed(prev)
                               if getattr(o, k) is not None), None)
    if any(v is None for v in cur):
        return None
    deltas = []
    for k in DELTAS:
        vals = [getattr(o, k) for o in prev if getattr(o, k) is not None]
        deltas.append(cur[CURRENT.index(k)] - float(np.mean(vals)) if vals else 0.0)
    return np.array([float(v) for v in cur] + deltas, dtype=float)


def normalize_score(s: float, p50: float, p01: float) -> float:
    """Score 0–1: 0 na mediana do treino, 1 em p01 ou abaixo."""
    den = p50 - p01
    if den <= 0:
        return 0.0
    return float(np.clip((p50 - s) / den, 0.0, 1.0))


class VitalsIForest:
    """Wrapper de inferência; desativado se o modelo não existir."""

    def __init__(self, models_dir: Path | None = None, model_name: str | None = None) -> None:
        st = get_settings()
        self.dir = Path(models_dir) if models_dir else st.models_dir
        self.name = model_name or st.vitals_iforest_model or MODEL_NAME
        self.pipeline = None
        self.meta: dict = {}
        self._warned = False

    @property
    def carry_forward(self) -> bool:
        """Se o modelo foi treinado repetindo o último valor conhecido (dados reais)."""
        return bool(self.meta.get("carry_forward", False))

    @property
    def enabled(self) -> bool:
        """Indica se o modelo foi carregado."""
        return self.pipeline is not None

    def load(self) -> bool:
        """Carrega modelo e metadados; retorna False (com aviso único) se ausentes."""
        import joblib

        mp, jp = self.dir / f"{self.name}.joblib", self.dir / f"{self.name}.json"
        if not mp.exists() or not jp.exists():
            if not self._warned:
                log.warning("modelo %s não encontrado em %s; IForest desativado",
                            self.name, self.dir)
                self._warned = True
            self.pipeline = None
            return False
        self.pipeline = joblib.load(mp)
        self.meta = json.loads(jp.read_text())
        log.info("IForest %s carregado (%s)", self.name, self.meta.get("source", "?"))
        return True

    def raw_score(self, features: np.ndarray) -> float:
        """Score bruto do Isolation Forest (menor = mais anômalo)."""
        x = np.asarray(features, dtype=float).reshape(1, -1)
        return float(self.pipeline.score_samples(x)[0])

    def score(self, features: np.ndarray, threshold_key: str = "threshold"
              ) -> tuple[bool, float]:
        """Retorna (é_anomalia, score normalizado 0–1).

        `threshold_key` escolhe o limiar nos metadados (`threshold` = percentil 0,5;
        `p0_1` = percentil 0,1); se a chave não existir, usa `threshold`.
        """
        if self.pipeline is None:
            if not self._warned:
                log.warning("IForest desativado (modelo não carregado)")
                self._warned = True
            return False, 0.0
        s = self.raw_score(features)
        thr = self.meta.get(threshold_key, self.meta["threshold"])
        return s < thr, normalize_score(s, self.meta["p50"], self.meta["p01"])


def score_percentiles(s: np.ndarray) -> dict:
    """Limiares usados na inferência, a partir de scores brutos."""
    return {"threshold": float(np.percentile(s, 0.5)),
            "p0_1": float(np.percentile(s, 0.1)), "p01": float(np.percentile(s, 1)),
            "p50": float(np.percentile(s, 50))}


def train_and_save(X: np.ndarray, models_dir: Path, model_name: str = MODEL_NAME,
                   X_val: np.ndarray | None = None, extra_meta: dict | None = None) -> dict:
    """Treina o pipeline, calcula limiares e salva .joblib e .json.

    Com `X_val`, os limiares vêm dos scores da validação (fora do treino) e os do treino
    ficam em `train_percentiles`.
    """
    from datetime import datetime

    import joblib
    from sklearn.ensemble import IsolationForest
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    pipe = Pipeline([("scaler", StandardScaler()),
                     ("iforest", IsolationForest(n_estimators=200, contamination="auto",
                                                 random_state=42))])
    pipe.fit(X)
    train_pct = score_percentiles(pipe.score_samples(X))
    meta = dict(train_pct)
    if X_val is not None and len(X_val):
        meta = score_percentiles(pipe.score_samples(X_val))
        meta |= {"train_percentiles": train_pct, "n_val_samples": int(len(X_val))}
    meta |= {"trained_at": datetime.now(UTC).isoformat(), "n_samples": int(len(X))}
    meta |= extra_meta or {}
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, models_dir / f"{model_name}.joblib")
    (models_dir / f"{model_name}.json").write_text(json.dumps(meta, indent=2))
    return meta


def features_from_series(vitals: list[VitalObservation],
                         carry_forward: bool = False) -> list[np.ndarray]:
    """Features de cada ponto de uma série ordenada."""
    out = []
    for i in range(5, len(vitals)):
        f = build_features(vitals[i - 5: i + 1], carry_forward)
        if f is not None:
            out.append(f)
    return out
