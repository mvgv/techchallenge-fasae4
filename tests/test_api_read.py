from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from medwatch import db
from medwatch.api.main import app
from medwatch.contracts import Alert, VitalObservation

pytestmark = pytest.mark.skipif(not db.ping(), reason="banco indisponível")

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


@pytest.fixture()
def env():
    pid = f"T-{uuid4().hex[:8]}"
    db.upsert_patient(pid, "Teste", "L1")
    yield TestClient(app), pid


def _alert(pid: str) -> Alert:
    return Alert(patient_id=pid, level="warning", risk_score=50.0, title="t",
                 summary="s", evidence_ids=[], created_at=T0, updated_at=T0)


def test_ack_confirmed_then_409(env):
    client, pid = env
    a = _alert(pid)
    db.insert_alert(a, T0)
    r = client.post(f"/alerts/{a.alert_id}/ack",
                    json={"user": "dr", "decision": "confirmed", "note": "ok"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "acknowledged"
    assert body["acked_by"] == "dr" and body["ack_note"] == "ok"
    assert body["acked_at"] is not None
    r2 = client.post(f"/alerts/{a.alert_id}/ack",
                     json={"user": "dr", "decision": "dismissed"})
    assert r2.status_code == 409


def test_ack_dismissed_and_list_filter(env):
    client, pid = env
    a = _alert(pid)
    db.insert_alert(a, T0)
    assert [x["alert_id"] for x in client.get(
        "/alerts", params={"status": "open", "patient_id": pid}).json()] == [str(a.alert_id)]
    r = client.post(f"/alerts/{a.alert_id}/ack",
                    json={"user": "dr", "decision": "dismissed"})
    assert r.json()["status"] == "dismissed"
    assert client.get("/alerts", params={"status": "open", "patient_id": pid}).json() == []


def test_ack_unknown_alert_404(env):
    client, _ = env
    r = client.post(f"/alerts/{uuid4()}/ack", json={"user": "dr", "decision": "confirmed"})
    assert r.status_code == 404


def test_vitals_since_until_and_default_window(env):
    client, pid = env
    for h in (0, 5, 8, 10):
        db.insert_vital(VitalObservation(patient_id=pid, ts=T0 + timedelta(hours=h), hr=80), None)
    # padrão: últimas 6 h a partir do último evento (T0+10h) -> 5h, 8h e 10h (0h fica de fora)
    r = client.get(f"/patients/{pid}/vitals")
    assert r.status_code == 200 and len(r.json()) == 3
    r = client.get(f"/patients/{pid}/vitals", params={"since": (T0 + timedelta(hours=1)).isoformat(),
                                                      "until": (T0 + timedelta(hours=9)).isoformat()})
    assert len(r.json()) == 2  # 5h e 8h
    assert r.json()[0]["ts"].startswith("2026-01-01T17:00")


def test_vitals_unknown_patient_404(env):
    client, _ = env
    assert client.get("/patients/NOPE-xyz/vitals").status_code == 404


def test_evidence_and_risk_empty(env):
    client, pid = env
    assert client.get(f"/patients/{pid}/evidence").json() == []
    assert client.get(f"/patients/{pid}/risk").json() == []
