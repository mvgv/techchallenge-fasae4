from datetime import UTC, datetime
from uuid import uuid4

import httpx

from medwatch.alerts.channels import (
    ConsoleChannel,
    EmailChannel,
    TeamsChannel,
    dispatch,
    teams_payload,
)
from medwatch.alerts.worker import AlertWorker
from medwatch.contracts import Alert, Severity


def make_alert(**kw) -> Alert:
    now = datetime.now(UTC)
    base = dict(patient_id="p0001", level=Severity.critical, risk_score=87.0,
                title="[CRÍTICO] Teste", summary="Risco 87/100.\n• linha",
                evidence_ids=[uuid4()], created_at=now, updated_at=now)
    base.update(kw)
    return Alert(**base)


def test_teams_payload():
    p = teams_payload(make_alert(), "http://x")
    content = p["attachments"][0]["content"]
    assert content["type"] == "AdaptiveCard"
    assert content["actions"][0]["url"] == "http://x/?patient=p0001"


def test_teams_failure_does_not_block_email():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(500 if "teams" in req.url.host else 200)

    t = httpx.MockTransport(handler)
    chans = [TeamsChannel("https://teams.test/hook", transport=t),
             EmailChannel("https://mail.test/hook", "a@b.c", transport=t)]
    res = dispatch(chans, make_alert())
    assert res == {"teams": False, "email": True}
    assert sum("teams" in c for c in calls) == 2  # 2 tentativas
    assert any("mail" in c for c in calls)


def test_email_body_has_br():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen.update(__import__("json").loads(req.content))
        return httpx.Response(200)

    EmailChannel("https://mail.test/h", "a@b.c", transport=httpx.MockTransport(handler)
                 ).send(make_alert())
    assert "<br>" in seen["html"] and seen["to"] == "a@b.c"


class Rec:
    name = "rec"

    def __init__(self):
        self.titles = []

    def send(self, alert):
        self.titles.append(alert.title)


def test_worker_prefix_and_escalation():
    rec = Rec()

    class FakeDb:
        updated = []

        def alerts_to_escalate(self, m):
            a = make_alert()
            return [dict(a.model_dump(), alert_id=a.alert_id)]

        def update_alert(self, aid, **f):
            self.updated.append((aid, f))

    db = FakeDb()
    w = AlertWorker([ConsoleChannel(), rec], db, escalation_minutes=5)
    w.handle("alerts", make_alert(event="escalated").model_dump(mode="json"))
    assert rec.titles[-1].startswith("ESCALONADO: ")
    assert w.escalate_pending() == 1
    assert rec.titles[-1].startswith("SEM RESPOSTA: ")
    assert db.updated[0][1] == {"escalated": True}
