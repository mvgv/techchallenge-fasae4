"""Regras de prescrição: dose, alto risco, classe duplicada, interações e rajadas."""
from __future__ import annotations

import math
import re
from collections import deque
from datetime import datetime, timedelta

from unidecode import unidecode

from medwatch.anomaly.streaming_stats import Cooldown
from medwatch.contracts import Evidence, Modality, PrescriptionEvent, Severity

_PAREN = re.compile(r"\([^)]*\)")
_DOSE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ui|ml|meq|%|u)?\b")
_MODEL = "prescription_rules"


def normalize_drug(name: str) -> str:
    """Minúsculas, sem acento, sem dose/unidade nem parênteses, espaços colapsados."""
    s = _PAREN.sub(" ", unidecode(name).lower())
    s = _DOSE.sub(" ", s)
    return " ".join(s.split())


def _fmt(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _fmt_ratio(r: float) -> str:
    return f"{r:.1f}".replace(".", ",")


class _State:
    def __init__(self) -> None:
        self.active: dict[str, PrescriptionEvent] = {}
        self.changes: deque[datetime] = deque()


class PrescriptionMonitor:
    """Avalia eventos de prescrição por paciente."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.high_alert = [normalize_drug(x) for x in cfg.get("high_alert", [])]
        self.classes = {c: [normalize_drug(t) for t in terms]
                        for c, terms in cfg.get("classes", {}).items()}
        self.interactions = cfg.get("interactions", [])
        self.ratio_high = cfg.get("dose_change_ratio_high", 1.5)
        self.ratio_low = cfg.get("dose_change_ratio_low", 0.5)
        self.burst_n = cfg.get("burst_changes_24h", 4)
        self._states: dict[str, _State] = {}
        self._cooldown = Cooldown()

    def _class_of(self, drug: str) -> str | None:
        for cls, terms in self.classes.items():
            if any(t and t in drug for t in terms):
                return cls
        return None

    def _matches(self, drug: str, ref: str) -> bool:
        if ref in self.classes:
            return self._class_of(drug) == ref
        ref_n = normalize_drug(ref)
        return bool(ref_n) and ref_n in drug

    def _ev(self, ev: PrescriptionEvent, typ: str, score: float, sev: Severity,
            text: str, payload: dict) -> Evidence:
        return Evidence(patient_id=ev.patient_id, modality=Modality.prescription, type=typ,
                        score=score, severity=sev, ts_start=ev.ts, explanation=text,
                        source_ref=f"rx:{ev.rx_id}", model_name=_MODEL, payload=payload)

    def process(self, ev: PrescriptionEvent) -> list[Evidence]:
        """Processa um evento e devolve as evidências geradas."""
        st = self._states.setdefault(ev.patient_id, _State())
        drug = normalize_drug(ev.drug)
        out: list[Evidence] = []

        if ev.action == "stop":
            st.active.pop(drug, None)
            return out

        prev = st.active.get(drug)
        if prev is not None and prev.dose and ev.dose and ev.dose != prev.dose:
            ratio = ev.dose / prev.dose
            if ratio >= self.ratio_high or ratio <= self.ratio_low:
                unit = f" {ev.unit}" if ev.unit else ""
                text = (f"Dose de {drug} alterada de {_fmt(prev.dose)} para "
                        f"{_fmt(ev.dose)}{unit} ({_fmt_ratio(ratio)}x)")
                out.append(self._ev(
                    ev, "rx_dose_change", min(1.0, abs(math.log2(ratio)) / 2),
                    Severity.warning, text,
                    dict(drug=drug, old_dose=prev.dose, new_dose=ev.dose, ratio=ratio)))

        if ev.action == "start" and any(h and h in drug for h in self.high_alert):
            out.append(self._ev(ev, "rx_high_alert_start", 0.35, Severity.info,
                                f"Início de medicamento de alto risco: {drug}",
                                dict(drug=drug)))

        cls = self._class_of(drug)
        others = [d for d in st.active if d != drug]
        if cls:
            same = [d for d in others if self._class_of(d) == cls]
            if same:
                out.append(self._ev(
                    ev, "rx_duplicate_class", 0.3, Severity.info,
                    f"Medicamentos da mesma classe ({cls}) ativos: "
                    f"{', '.join(same + [drug])}",
                    dict(drug_class=cls, drugs=same + [drug])))

        for other in others:
            for rule in self.interactions:
                a, b = rule["a"], rule["b"]
                if ((self._matches(drug, a) and self._matches(other, b))
                        or (self._matches(drug, b) and self._matches(other, a))):
                    out.append(self._ev(
                        ev, "rx_interaction", 0.7, Severity.warning,
                        f"{other.capitalize()} + {drug}: {rule['note'].lower()}",
                        dict(drugs=[other, drug], note=rule["note"])))
                    break

        if ev.action in ("start", "change"):
            st.changes.append(ev.ts)
            while st.changes and ev.ts - st.changes[0] > timedelta(hours=24):
                st.changes.popleft()
            if (len(st.changes) >= self.burst_n
                    and self._cooldown.ready((ev.patient_id, "burst"), ev.ts, 12 * 60)):
                out.append(self._ev(
                    ev, "rx_change_burst", 0.4, Severity.warning,
                    f"{len(st.changes)} alterações de prescrição em 24 h",
                    dict(changes_24h=len(st.changes))))

        st.active[drug] = ev
        return out
