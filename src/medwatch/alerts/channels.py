"""Canais de notificação de alertas: console, Teams e e-mail (Logic App)."""
from __future__ import annotations

import html
import logging
from typing import Protocol

import httpx

from medwatch.contracts import Alert

log = logging.getLogger(__name__)

TIMEOUT = 10.0
ATTEMPTS = 2


class Channel(Protocol):
    name: str

    def send(self, alert: Alert) -> None: ...


def teams_payload(alert: Alert, dashboard_url: str) -> dict:
    color = {"critical": "Attention", "warning": "Warning", "info": "Accent"}[
        str(alert.level.value)]
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard", "version": "1.4",
                "body": [
                    {"type": "TextBlock", "text": alert.title, "weight": "Bolder",
                     "size": "Medium", "color": color, "wrap": True},
                    {"type": "TextBlock", "text": alert.summary, "wrap": True},
                    {"type": "FactSet", "facts": [
                        {"title": "Paciente", "value": alert.patient_id},
                        {"title": "Risco", "value": f"{alert.risk_score:.0f}/100"},
                        {"title": "Evento", "value": alert.event}]},
                ],
                "actions": [{"type": "Action.OpenUrl", "title": "Abrir no painel",
                             "url": f"{dashboard_url}/?patient={alert.patient_id}"}],
            },
        }],
    }


def _post(url: str, payload: dict, transport: httpx.BaseTransport | None) -> None:
    last: Exception | None = None
    for _ in range(ATTEMPTS):
        try:
            with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
                client.post(url, json=payload).raise_for_status()
            return
        except httpx.HTTPError as exc:
            last = exc
    raise last  # type: ignore[misc]


class ConsoleChannel:
    name = "console"

    def send(self, alert: Alert) -> None:
        log.warning("ALERTA %s\n%s", alert.title, alert.summary)


class TeamsChannel:
    name = "teams"

    def __init__(self, webhook_url: str, dashboard_url: str = "http://localhost:8501",
                 transport: httpx.BaseTransport | None = None) -> None:
        self.url, self.dashboard_url, self.transport = webhook_url, dashboard_url, transport

    def send(self, alert: Alert) -> None:
        _post(self.url, teams_payload(alert, self.dashboard_url), self.transport)


class EmailChannel:
    name = "email"

    def __init__(self, logic_app_url: str, to: str,
                 transport: httpx.BaseTransport | None = None) -> None:
        self.url, self.to, self.transport = logic_app_url, to, transport

    def send(self, alert: Alert) -> None:
        body = html.escape(alert.summary).replace("\n", "<br>")
        _post(self.url, {"to": self.to, "subject": alert.title, "html": body},
              self.transport)


def build_channels(settings) -> list[Channel]:
    channels: list[Channel] = [ConsoleChannel()]
    if settings.teams_webhook_url:
        channels.append(TeamsChannel(settings.teams_webhook_url, settings.dashboard_url))
    if settings.logic_app_email_url and settings.alert_email_to:
        channels.append(EmailChannel(settings.logic_app_email_url, settings.alert_email_to))
    return channels


def dispatch(channels: list[Channel], alert: Alert) -> dict[str, bool]:
    """Envia a todos os canais; falha de um não impede os demais."""
    results: dict[str, bool] = {}
    for ch in channels:
        try:
            ch.send(alert)
            results[ch.name] = True
        except Exception:
            log.exception("falha no canal %s", ch.name)
            results[ch.name] = False
    return results
