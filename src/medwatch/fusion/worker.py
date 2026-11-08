"""Worker de fusão: persiste evidências, calcula o risco e cria/escala alertas."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from types import ModuleType

from medwatch import db as default_db
from medwatch.bus import Bus
from medwatch.config import get_settings, load_yaml
from medwatch.contracts import SEVERITY_ORDER, Alert, Evidence, Severity
from medwatch.fusion.engine import FusionEngine, RiskResult
from medwatch.logging_setup import setup_logging

log = logging.getLogger(__name__)

GROUP = "worker-fusion"
STREAMS = ["evidence"]
TOP_SNAPSHOT = 10
TOP_SUMMARY = 3
LEVEL_PT = {"critical": "CRÍTICO", "warning": "ATENÇÃO", "info": "INFORMATIVO"}


def _num(x: float) -> str:
    return f"{x:g}".replace(".", ",")


class FusionWorker:
    def __init__(self, bus: Bus, db_module: ModuleType | object = default_db,
                 cfg: dict | None = None, min_level: str | None = None,
                 cooldown_minutes: int | None = None) -> None:
        settings = get_settings()
        self.bus, self.db = bus, db_module
        self.cfg = cfg or load_yaml("fusion")
        self.engine = FusionEngine(self.cfg)
        self.min_level = min_level or settings.alert_min_level
        self.cooldown = timedelta(minutes=cooldown_minutes if cooldown_minutes is not None
                                  else settings.alert_cooldown_minutes)
        self._labels: dict[str, str] = self.cfg.get("labels", {})
        self._rule_labels = {r["name"]: r.get("label", r["name"])
                             for r in self.cfg.get("rules", [])}

    # ---------- estado ----------

    def rehydrate(self) -> int:
        """Recarrega do banco a janela de evidências de cada paciente."""
        evs = self.db.recent_evidence_all(self.cfg["window_minutes"])
        for ev in sorted(evs, key=lambda e: e.ts_start):
            self.engine.windows.setdefault(ev.patient_id, []).append(ev)
        log.info("janela reidratada: %d evidências de %d pacientes",
                 len(evs), len(self.engine.windows))
        return len(evs)

    # ---------- textos ----------

    def _label(self, typ: str) -> str:
        return self._labels.get(typ, typ)

    def _display_name(self, patient_id: str) -> str:
        p = self.db.get_patient(patient_id)
        return (p or {}).get("display_name") or patient_id

    def title(self, result: RiskResult) -> str:
        """Título do alerta: nível, paciente e maior contribuição."""
        top = result.contributions[0]["type"] if result.contributions else "risco"
        return (f"[{LEVEL_PT[result.level]}] {self._display_name(result.patient_id)} "
                f"({result.patient_id}) – {self._label(top)}")

    def summary(self, result: RiskResult) -> str:
        """Resumo multilinha: risco, regras disparadas e 3 maiores contribuições."""
        lines = [f"Risco {_num(result.risk)}/100."]
        if result.rules_fired:
            rules = "; ".join(self._rule_labels.get(r, r) for r in result.rules_fired)
            lines.append(f"Regras: {rules}.")
        for c in result.contributions[:TOP_SUMMARY]:
            lines.append(f"• {self._label(c['type'])}: {c['explanation']}")
        return "\n".join(lines)

    # ---------- alertas ----------

    @staticmethod
    def _ids(result: RiskResult) -> list[str]:
        return [c["evidence_id"] for c in result.contributions if c["contrib"] > 0]

    @staticmethod
    def _alert_from_row(row: dict, event: str) -> Alert:
        return Alert(**{k: row[k] for k in Alert.model_fields if k in row}, event=event)

    def decide(self, result: RiskResult) -> Alert | None:
        """Cria, escala ou atualiza o alerta do paciente; retorna o que foi publicado."""
        if SEVERITY_ORDER[result.level] < SEVERITY_ORDER[self.min_level]:
            return None
        pid = result.patient_id
        open_alert = self.db.get_open_alert(pid)
        if open_alert is not None:
            ids = list(dict.fromkeys([str(i) for i in open_alert["evidence_ids"]]
                                     + self._ids(result)))
            if SEVERITY_ORDER[result.level] > SEVERITY_ORDER[str(open_alert["level"])]:
                row = self.db.update_alert(
                    open_alert["alert_id"], level=result.level, risk_score=result.risk,
                    evidence_ids=ids, title=self.title(result), summary=self.summary(result))
                alert = self._alert_from_row(row, "escalated")
                self.bus.publish("alerts", alert)
                log.info("alerta escalado: %s", alert.title)
                return alert
            fields: dict = {"evidence_ids": ids}
            if result.risk > float(open_alert["risk_score"]):
                fields["risk_score"] = result.risk
            self.db.update_alert(open_alert["alert_id"], **fields)
            return None

        last = self.db.last_closed_alert(pid)
        if (last is not None and result.ts - last["event_ts"] < self.cooldown
                and SEVERITY_ORDER[str(last["level"])] >= SEVERITY_ORDER[result.level]):
            return None
        now = datetime.now(UTC)
        alert = Alert(patient_id=pid, level=Severity(result.level), risk_score=result.risk,
                      title=self.title(result), summary=self.summary(result),
                      evidence_ids=self._ids(result), created_at=now, updated_at=now)
        self.db.insert_alert(alert, result.ts)
        self.bus.publish("alerts", alert)
        log.info("alerta criado: %s", alert.title)
        return alert

    # ---------- fluxo ----------

    def process(self, ev: Evidence) -> tuple[RiskResult, Alert | None]:
        """Persiste a evidência, atualiza o risco e decide o alerta."""
        self.db.insert_evidence(ev)
        result = self.engine.add(ev)
        self.db.insert_risk_snapshot(result.patient_id, result.ts, result.risk, result.level,
                                     result.contributions[:TOP_SNAPSHOT])
        return result, self.decide(result)

    def handle(self, stream: str, payload: dict) -> None:
        if stream == "evidence":
            self.process(Evidence(**payload))


def main() -> None:
    setup_logging("worker-fusion")
    worker = FusionWorker(Bus())
    worker.rehydrate()
    log.info("worker-fusion iniciado (min_level=%s)", worker.min_level)
    worker.bus.consume(STREAMS, GROUP, worker.handle)


if __name__ == "__main__":
    main()
