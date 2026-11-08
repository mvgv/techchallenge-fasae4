"""NEWS2 (escala 1 de SpO2)."""
from __future__ import annotations

from medwatch.contracts import VitalObservation


def score_rr(v: float) -> int:
    if v <= 8:
        return 3
    if v <= 11:
        return 1
    if v <= 20:
        return 0
    if v <= 24:
        return 2
    return 3


def score_spo2(v: float) -> int:
    if v <= 91:
        return 3
    if v <= 93:
        return 2
    if v <= 95:
        return 1
    return 0


def score_sbp(v: float) -> int:
    if v <= 90:
        return 3
    if v <= 100:
        return 2
    if v <= 110:
        return 1
    if v <= 219:
        return 0
    return 3


def score_hr(v: float) -> int:
    if v <= 40:
        return 3
    if v <= 50:
        return 1
    if v <= 90:
        return 0
    if v <= 110:
        return 1
    if v <= 130:
        return 2
    return 3


def score_temp(v: float) -> int:
    if v <= 35.0:
        return 3
    if v <= 36.0:
        return 1
    if v <= 38.0:
        return 0
    if v <= 39.0:
        return 1
    return 2


def news2(obs: VitalObservation) -> dict:
    """Calcula NEWS2. Parâmetros ausentes são ignorados e listados em 'missing'."""
    params: dict[str, int] = {}
    missing: list[str] = []
    for name, fn in [
        ("rr", score_rr),
        ("spo2", score_spo2),
        ("sbp", score_sbp),
        ("hr", score_hr),
        ("temp", score_temp),
    ]:
        v = getattr(obs, name)
        if v is None:
            missing.append(name)
        else:
            params[name] = fn(v)
    params["consciousness"] = 0 if obs.consciousness == "A" else 3
    params["oxygen"] = 2 if obs.on_oxygen else 0
    total = sum(params.values())
    if total >= 7:
        band = "high"
    elif total >= 5:
        band = "medium"
    elif any(s == 3 for s in params.values()):
        band = "low_medium"
    else:
        band = "low"
    return {"total": total, "band": band, "params": params, "missing": missing}
