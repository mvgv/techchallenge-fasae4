"""Worker de alertas: envia aos canais e escalona alertas críticos sem resposta."""
from __future__ import annotations

import logging
import threading
from types import ModuleType

from medwatch import db as default_db
from medwatch.alerts.channels import Channel, build_channels, dispatch
from medwatch.bus import Bus
from medwatch.config import get_settings
from medwatch.contracts import Alert
from medwatch.logging_setup import setup_logging

log = logging.getLogger(__name__)

GROUP = "worker-alerts"
STREAMS = ["alerts"]
ESCALATION_INTERVAL = 30.0


class AlertWorker:
    def __init__(self, channels: list[Channel], db_module: ModuleType | object = default_db,
                 escalation_minutes: int | None = None) -> None:
        self.channels, self.db = channels, db_module
        self.escalation_minutes = (escalation_minutes if escalation_minutes is not None
                                   else get_settings().alert_escalation_minutes)

    def notify(self, alert: Alert, prefix: str = "") -> dict[str, bool]:
        if prefix:
            alert = alert.model_copy(update={"title": prefix + alert.title})
        return dispatch(self.channels, alert)

    def handle(self, stream: str, payload: dict) -> None:
        if stream != "alerts":
            return
        alert = Alert(**payload)
        self.notify(alert, "ESCALONADO: " if alert.event == "escalated" else "")

    def escalate_pending(self) -> int:
        rows = self.db.alerts_to_escalate(self.escalation_minutes)
        for row in rows:
            alert = Alert(**{k: row[k] for k in Alert.model_fields if k in row and k != "event"},
                          event="escalated")
            self.notify(alert, "SEM RESPOSTA: ")
            self.db.update_alert(row["alert_id"], escalated=True)
        return len(rows)

    def escalation_loop(self, stop: threading.Event) -> None:
        while not stop.wait(ESCALATION_INTERVAL):
            try:
                self.escalate_pending()
            except Exception:
                log.exception("falha no escalonamento")


def main() -> None:
    setup_logging("worker-alerts")
    worker = AlertWorker(build_channels(get_settings()))
    stop = threading.Event()
    threading.Thread(target=worker.escalation_loop, args=(stop,), daemon=True).start()
    log.info("worker-alerts iniciado (canais: %s)", [c.name for c in worker.channels])
    try:
        Bus().consume(STREAMS, GROUP, worker.handle)
    finally:
        stop.set()


if __name__ == "__main__":
    main()
