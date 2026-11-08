from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from medwatch import db
from medwatch.contracts import Alert, Evidence

pytestmark = pytest.mark.skipif(not db.ping(), reason="banco indisponível")

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_patient_evidence_and_alert_roundtrip():
    pid = f"T-{uuid4().hex[:8]}"
    db.upsert_patient(pid, "Teste", "L1")
    p = db.get_patient(pid)
    assert p["display_name"] == "Teste" and p["open_alerts"] == 0
    assert any(x["patient_id"] == pid for x in db.list_patients())

    ev = Evidence(patient_id=pid, modality="vitals", type="news2_high", score=0.8,
                  severity="critical", ts_start=T0, explanation="teste", model_name="t")
    db.insert_evidence(ev)
    db.insert_evidence(ev)  # idempotente
    rows = db.list_evidence(pid, None, 10)
    assert len(rows) == 1
    assert len(db.get_evidence_many([ev.evidence_id])) == 1
    assert any(e.evidence_id == ev.evidence_id for e in db.recent_evidence_all(30))

    now = datetime.now(UTC)
    al = Alert(patient_id=pid, level="critical", risk_score=80, title="t", summary="s",
               evidence_ids=[ev.evidence_id], created_at=now - timedelta(minutes=10),
               updated_at=now)
    db.insert_alert(al, T0)
    assert db.get_open_alert(pid)["alert_id"] == al.alert_id
    assert any(a["alert_id"] == al.alert_id for a in db.alerts_to_escalate(5))
    upd = db.update_alert(al.alert_id, status="acknowledged", acked_by="dr")
    assert upd["status"] == "acknowledged"
    assert db.get_open_alert(pid) is None
    assert db.last_closed_alert(pid)["alert_id"] == al.alert_id
    assert db.list_alerts("acknowledged", pid)
    with pytest.raises(ValueError):
        db.update_alert(al.alert_id, bogus=1)

    db.insert_risk_snapshot(pid, T0, 50.0, "warning", {"a": 1})
    db.insert_risk_snapshot(pid, T0, 60.0, "warning", {"a": 2})
    assert [r["risk_score"] for r in db.query_risk(pid)] == [60.0]
