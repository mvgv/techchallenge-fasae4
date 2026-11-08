"""Motor de fusão: combina evidências multimodais em um risco 0..100."""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from medwatch.contracts import Evidence


@dataclass
class RiskResult:
    patient_id: str
    ts: datetime                   # tempo de referência (evento mais recente do paciente)
    risk: float                    # 0..100
    level: str                     # none | info | warning | critical
    contributions: list[dict] = field(default_factory=list)  # ordenado desc
    rules_fired: list[str] = field(default_factory=list)
    floor_applied: bool = False


def _matches(ev: Evidence, item: dict) -> bool:
    if ev.type != item["type"]:
        return False
    return all(ev.payload.get(k) == v for k, v in (item.get("payload") or {}).items())


class FusionEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.windows: dict[str, list[Evidence]] = {}

    def add(self, ev: Evidence) -> RiskResult:
        w = self.windows.setdefault(ev.patient_id, [])
        w.append(ev)
        t_ref = max(e.ts_start for e in w)
        horizon = t_ref - timedelta(minutes=self.cfg["window_minutes"])
        w[:] = [e for e in w if e.ts_start >= horizon]
        return self.compute(ev.patient_id, t_ref)

    def _decay(self, ev: Evidence, t_ref: datetime) -> float:
        minutes = max(0.0, (t_ref - ev.ts_start).total_seconds() / 60)
        return math.exp(-minutes / self.cfg["tau_minutes"])

    def _weight(self, ev: Evidence) -> float:
        weight = self.cfg.get("weights", {}).get(ev.type)
        if weight is None:
            weight = self.cfg["default_weight_by_modality"][ev.modality.value]
        return weight

    def compute(self, patient_id: str, t_ref: datetime) -> RiskResult:
        cfg = self.cfg
        evidences = self.windows.get(patient_id, [])
        labels = cfg.get("labels", {})

        # 1-2. contribuição por evidência; só a maior por tipo
        best: dict[str, dict] = {}
        for ev in evidences:
            contrib = self._weight(ev) * ev.score * self._decay(ev, t_ref)
            cur = best.get(ev.type)
            if cur is None or contrib > cur["contrib"]:
                best[ev.type] = {
                    "type": ev.type,
                    "evidence_id": str(ev.evidence_id),
                    "contrib": contrib,
                    "explanation": ev.explanation or labels.get(ev.type, ev.type),
                }
        contributions = sorted(best.values(), key=lambda c: c["contrib"], reverse=True)

        # 3. combinação noisy-OR
        prod = 1.0
        for c in contributions:
            prod *= 1.0 - c["contrib"]
        risk_raw = 1.0 - prod

        # 4. regras multimodais
        rules_fired: list[str] = []
        for rule in cfg.get("rules", []):
            start = t_ref - timedelta(minutes=rule["window_minutes"])
            in_window = [e for e in evidences if start <= e.ts_start <= t_ref]
            if all(
                any(_matches(e, item) for e in in_window for item in group["any_of"])
                for group in rule["all_of"]
            ):
                rules_fired.append(rule["name"])
                risk_raw = min(1.0, risk_raw * rule["multiplier"])

        # 5. risco e nível
        levels = cfg["levels"]
        risk = round(100 * risk_raw, 1)

        def level_of(r: float) -> str:
            for name in ("critical", "warning", "info"):
                if r >= levels[name]:
                    return name
            return "none"

        level = level_of(risk)

        # 6. piso crítico
        floor_applied = False
        floor_types = set(cfg.get("floor_critical", []))
        if any(e.type in floor_types and self._decay(e, t_ref) >= 0.5 for e in evidences):
            floor_applied = True
            level = "critical"
            risk = max(risk, float(levels["critical"]))

        for c in contributions:
            c["contrib"] = round(c["contrib"], 4)
        return RiskResult(
            patient_id=patient_id,
            ts=t_ref,
            risk=risk,
            level=level,
            contributions=contributions,
            rules_fired=rules_fired,
            floor_applied=floor_applied,
        )
