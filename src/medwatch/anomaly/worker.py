"""Worker de anomalias: consome vitals, prescriptions e movement e publica evidências."""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from types import ModuleType

from medwatch import db as default_db
from medwatch.anomaly.filters import clean_observation
from medwatch.anomaly.iforest import VitalsIForest, build_features
from medwatch.anomaly.movement import MovementMonitor
from medwatch.anomaly.news2 import news2
from medwatch.anomaly.prescriptions import PrescriptionMonitor, normalize_drug
from medwatch.anomaly.streaming_stats import Cooldown, EwmaZ
from medwatch.bus import Bus
from medwatch.config import load_yaml
from medwatch.contracts import (
    Evidence,
    Modality,
    MovementSample,
    PrescriptionEvent,
    Severity,
    VitalObservation,
)
from medwatch.logging_setup import setup_logging

log = logging.getLogger(__name__)

GROUP = "worker-anomaly"
STREAMS = ["vitals", "prescriptions", "movement"]
SIGNALS = ("hr", "sbp", "dbp", "spo2", "rr", "temp")
_LABEL = {"hr": "FC", "sbp": "PAS", "dbp": "PAD", "spo2": "SpO₂", "rr": "FR", "temp": "Temp"}
_UNIT = {"hr": " bpm", "sbp": " mmHg", "dbp": " mmHg", "spo2": "%", "rr": " irpm", "temp": " °C"}
_NEWS_LABEL = {**_LABEL, "consciousness": "Consciência", "oxygen": "O₂"}
_BAND_RANK = {"low": 0, "low_medium": 1, "medium": 2, "high": 3}
_BAND_TEXT = {"low": "baixo", "low_medium": "baixo-médio", "medium": "médio", "high": "alto"}
_BAND_TYPE = {"low_medium": "news2_low_medium", "medium": "news2_medium", "high": "news2_high"}


def _num(x: float, fmt: str = "g") -> str:
    return format(x, fmt).replace(".", ",")


class _PatientState:
    def __init__(self, zcfg: dict) -> None:
        self.history: deque[VitalObservation] = deque(maxlen=60)
        self.ewma = {k: EwmaZ(zcfg.get("alpha", 0.1), zcfg.get("warmup", 20)) for k in SIGNALS}
        self.z_run = {k: 0 for k in SIGNALS}   # leituras consecutivas acima do limiar
        self.if_run = 0
        self.news_rank = 0
        self.news_ts: datetime | None = None


class AnomalyWorker:
    def __init__(self, bus: Bus, db_module: ModuleType | object = default_db,
                 iforest: VitalsIForest | None = None, cfg: dict | None = None) -> None:
        cfg = cfg or load_yaml("thresholds")
        self.bus, self.db = bus, db_module
        self.vcfg, self.iforest = cfg["vitals"], iforest
        self.cooldown = Cooldown()
        self.rx = PrescriptionMonitor(load_yaml("drugs"))
        self.mov = MovementMonitor(cfg["movement"])
        self._states: dict[str, _PatientState] = {}

    def _state(self, pid: str) -> _PatientState:
        if pid not in self._states:
            self._states[pid] = _PatientState(self.vcfg["zscore"])
        return self._states[pid]

    @staticmethod
    def _ev(obs: VitalObservation, typ: str, score: float, sev: Severity, text: str,
            model: str, payload: dict) -> Evidence:
        return Evidence(patient_id=obs.patient_id, modality=Modality.vitals, type=typ,
                        score=max(0.0, min(1.0, score)), severity=sev, ts_start=obs.ts,
                        explanation=text, model_name=model, payload=payload,
                        source_ref=f"vitals:{obs.patient_id}@{obs.ts.isoformat()}")

    def _news_evidence(self, obs: VitalObservation, st: _PatientState,
                       dropped: list[str]) -> Evidence | None:
        n = news2(obs)
        self.db.insert_vital(obs, n["total"])
        band, rank = n["band"], _BAND_RANK[n["band"]]
        repeat = self.vcfg["news2"]["repeat_minutes"]
        due = (rank >= 2 and st.news_ts is not None
               and (obs.ts - st.news_ts).total_seconds() >= repeat * 60)
        emit = rank > 0 and (rank > st.news_rank or due)
        st.news_rank = rank
        if not emit:
            return None
        st.news_ts = obs.ts
        parts = ", ".join(f"{_NEWS_LABEL[k]} {v}" for k, v in n["params"].items() if v > 0)
        return self._ev(
            obs, _BAND_TYPE[band], min(1.0, n["total"] / 10),
            Severity.critical if band == "high" else Severity.warning,
            f"NEWS2 = {n['total']} ({_BAND_TEXT[band]}): {parts}", "news2",
            {"total": n["total"], "band": band, "params": n["params"],
             "missing": n["missing"], "dropped": dropped})

    def process_vital(self, raw: VitalObservation) -> list[Evidence]:
        st = self._state(raw.patient_id)
        obs, dropped = clean_observation(raw, self.vcfg["physiologic_bounds"])
        st.history.append(obs)
        out: list[Evidence] = []

        news = self._news_evidence(obs, st, dropped)
        if news:
            out.append(news)

        zcfg = self.vcfg["zscore"]
        for k in SIGNALS:
            v = getattr(obs, k)
            if v is None:
                continue
            z = st.ewma[k].update(v)
            st.z_run[k] = st.z_run[k] + 1 if abs(z) >= zcfg["threshold"] else 0
            if st.z_run[k] >= zcfg.get("persistence", 1) and self.cooldown.ready(
                    (obs.patient_id, k), obs.ts, zcfg["cooldown_minutes"]):
                out.append(self._ev(
                    obs, "vital_zscore", abs(z) / 6, Severity.warning,
                    f"{_LABEL[k]} {_num(v)}{_UNIT[k]} fora do padrão do paciente "
                    f"(z = {_num(z, '.1f')})",
                    "ewma-z", {"vital": k, "value": v, "z": z}))

        if self.iforest is not None and self.iforest.enabled:
            feats = build_features(list(st.history), self.iforest.carry_forward)
            if feats is not None:
                icfg = self.vcfg["iforest"]
                anomalous, score = self.iforest.score(
                    feats, icfg.get("threshold_key", "threshold"))
                st.if_run = st.if_run + 1 if anomalous else 0
                if st.if_run >= icfg.get("persistence", 1) and self.cooldown.ready(
                        (obs.patient_id, "iforest"), obs.ts,
                        self.vcfg["iforest"]["cooldown_minutes"]):
                    out.append(self._ev(
                        obs, "vital_iforest", score, Severity.warning,
                        "Combinação de sinais vitais atípica para o padrão do paciente",
                        "iforest", {"features": [float(x) for x in feats]}))
        return out

    def process_rx(self, ev: PrescriptionEvent) -> list[Evidence]:
        self.db.insert_prescription(ev, normalize_drug(ev.drug))
        return self.rx.process(ev)

    def process_movement(self, s: MovementSample) -> list[Evidence]:
        self.db.insert_movement(s)
        return self.mov.process(s)

    def handle(self, stream: str, payload: dict) -> None:
        if stream == "vitals":
            evs = self.process_vital(VitalObservation(**payload))
        elif stream == "prescriptions":
            evs = self.process_rx(PrescriptionEvent(**payload))
        elif stream == "movement":
            evs = self.process_movement(MovementSample(**payload))
        else:
            return
        for e in evs:
            self.bus.publish("evidence", e)


def main() -> None:
    setup_logging("worker-anomaly")
    iforest = VitalsIForest()
    iforest.load()
    worker = AnomalyWorker(Bus(), iforest=iforest)
    log.info("worker-anomaly iniciado")
    worker.bus.consume(STREAMS, GROUP, worker.handle)


if __name__ == "__main__":
    main()
