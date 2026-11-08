"""Detecção de sons respiratórios (tosse, chiado etc.) com AST/AudioSet."""
from collections.abc import Callable
from pathlib import Path

import librosa

SR = 16000
BREATHING_LABEL = "Breathing"
BREATHING_MIN_SCORE = 0.6


class RespiratoryEventDetector:
    """Classifica janelas de áudio e agrega os rótulos-alvo."""

    MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"

    def __init__(self, cfg: dict, clf: Callable | None = None):
        """Cria o detector; `clf` injetável para testes (senão carrega o AST)."""
        if clf is None:
            from transformers import pipeline

            clf = pipeline("audio-classification", model=self.MODEL, top_k=15)
        self.clf = clf
        self.cfg = cfg

    def detect(self, wav: Path) -> list[dict]:
        """Retorna [{label, max_score, windows:[{t_start, score}]}] para rótulos-alvo."""
        y, sr = librosa.load(wav, sr=SR)
        win, hop = int(self.cfg["window_s"] * sr), int(self.cfg["hop_s"] * sr)
        hits: dict[str, list] = {}
        for start in range(0, max(1, len(y) - win + 1), hop):
            chunk = y[start:start + win].astype("float32")
            for p in self.clf({"raw": chunk, "sampling_rate": sr}):
                if p["label"] in self.cfg["labels"] and p["score"] >= self.cfg["min_score"]:
                    hits.setdefault(p["label"], []).append(
                        {"t_start": start / sr, "score": p["score"]}
                    )
        out = [
            {"label": k, "max_score": max(w["score"] for w in v), "windows": v}
            for k, v in hits.items()
        ]
        return [
            e for e in out
            if e["label"] != BREATHING_LABEL or e["max_score"] >= BREATHING_MIN_SCORE
        ]
