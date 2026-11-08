"""Estatística em streaming: EWMA z-score e controle de cooldown."""

import math
from datetime import datetime


class EwmaZ:
    """Média e variância exponenciais; z calculado ANTES de atualizar."""

    def __init__(self, alpha: float = 0.1, warmup: int = 20):
        self.alpha, self.warmup = alpha, warmup
        self.mean: float | None = None
        self.var = 0.0
        self.n = 0

    def update(self, x: float) -> float:
        if self.mean is None:
            self.mean, self.n = x, 1
            return 0.0
        diff = x - self.mean
        z = diff / math.sqrt(self.var) if self.n >= self.warmup and self.var > 1e-6 else 0.0
        incr = self.alpha * diff
        self.mean += incr
        self.var = (1 - self.alpha) * (self.var + diff * incr)
        self.n += 1
        return z


class Cooldown:
    """Controla reemissão por chave usando tempo do evento."""

    def __init__(self) -> None:
        self.last: dict[tuple, datetime] = {}

    def ready(self, key: tuple, ts: datetime, minutes: float) -> bool:
        prev = self.last.get(key)
        if prev is None or (ts - prev).total_seconds() >= minutes * 60:
            self.last[key] = ts
            return True
        return False
