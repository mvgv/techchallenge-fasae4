"""Regras de movimentação: inatividade, agitação noturna e saída do leito."""
from __future__ import annotations

from collections import deque

import numpy as np

from medwatch.anomaly.streaming_stats import Cooldown
from medwatch.contracts import Evidence, Modality, MovementSample, Severity

_MODEL = "movement-rules"
_COOLDOWN_MIN = 30
_HISTORY_MAX = 24 * 60


class _State:
    def __init__(self) -> None:
        self.idle_minutes = 0
        self.idle_emitted = False
        self.history: deque[float] = deque(maxlen=_HISTORY_MAX)
        self.in_bed: bool | None = None


class MovementMonitor:
    """Avalia amostras de movimento por paciente. O horário usa `ts` em UTC (ver DECISOES.md)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.idle_max = cfg.get("inactivity_activity_max", 5)
        self.idle_minutes = cfg.get("inactivity_minutes", 120)
        self.night_start = cfg.get("night_start_hour", 23)
        self.night_end = cfg.get("night_end_hour", 6)
        self.fixed = cfg.get("night_agitation_fixed", 80)
        self.min_history = cfg.get("night_agitation_min_history", 60)
        self._states: dict[str, _State] = {}
        self._cooldown = Cooldown()

    def is_night(self, hour: int) -> bool:
        if self.night_start > self.night_end:  # janela cruza a meia-noite
            return hour >= self.night_start or hour < self.night_end
        return self.night_start <= hour < self.night_end

    def _ev(self, s: MovementSample, typ: str, score: float, text: str,
            payload: dict) -> Evidence:
        return Evidence(patient_id=s.patient_id, modality=Modality.movement, type=typ,
                        score=score, severity=Severity.warning, ts_start=s.ts,
                        explanation=text, source_ref=f"movement:{s.patient_id}@{s.ts.isoformat()}",
                        model_name=_MODEL, payload=payload)

    def process(self, s: MovementSample) -> list[Evidence]:
        """Processa uma amostra (um minuto) e devolve as evidências geradas."""
        st = self._states.setdefault(s.patient_id, _State())
        night = self.is_night(s.ts.hour)
        out: list[Evidence] = []

        # inatividade (só fora do horário noturno)
        if not night and s.activity_count <= self.idle_max:
            st.idle_minutes += 1
            if st.idle_minutes >= self.idle_minutes and not st.idle_emitted:
                st.idle_emitted = True
                m = st.idle_minutes
                out.append(self._ev(
                    s, "movement_inactivity", min(1.0, m / (2 * self.idle_minutes)),
                    f"Paciente sem movimento relevante há {m} minutos durante o dia",
                    {"minutes": m}))
        else:
            st.idle_minutes = 0
            st.idle_emitted = False

        # agitação noturna
        if night:
            thr = float(self.fixed)
            if len(st.history) >= self.min_history:
                thr = max(thr, float(np.percentile(st.history, 95)))
            if s.activity_count > thr and self._cooldown.ready(
                    (s.patient_id, "agitation"), s.ts, _COOLDOWN_MIN):
                score = min(1.0, max(0.0, s.activity_count / 100))
                out.append(self._ev(
                    s, "movement_night_agitation", score,
                    f"Agitação noturna: atividade {s.activity_count:g} acima do limiar "
                    f"{thr:.0f}", {"activity": s.activity_count, "threshold": thr}))
        st.history.append(s.activity_count)

        # saída do leito à noite
        if (night and st.in_bed is True and s.in_bed is False
                and self._cooldown.ready((s.patient_id, "bed_exit"), s.ts, _COOLDOWN_MIN)):
            out.append(self._ev(s, "movement_bed_exit", 0.6,
                                "Paciente saiu do leito durante a noite", {}))
        if s.in_bed is not None:
            st.in_bed = s.in_bed
        return out
