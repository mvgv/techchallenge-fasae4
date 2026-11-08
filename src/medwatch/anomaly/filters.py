"""Filtro fisiológico: descarta valores fora dos limites (artefatos de sensor)."""
from __future__ import annotations

import logging

from medwatch.contracts import VitalObservation

log = logging.getLogger(__name__)


def clean_observation(
    obs: VitalObservation, bounds: dict[str, list[float]]
) -> tuple[VitalObservation, list[str]]:
    """Troca por None os campos fora de `bounds`; devolve também os campos descartados."""
    updates: dict[str, None] = {}
    for name, (lo, hi) in bounds.items():
        v = getattr(obs, name, None)
        if v is not None and not (lo <= v <= hi):
            updates[name] = None
    if updates:
        log.info(
            "campos descartados por limite fisiológico: %s (paciente %s)",
            sorted(updates),
            obs.patient_id,
        )
    return obs.model_copy(update=updates), list(updates)
