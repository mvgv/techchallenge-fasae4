import json
from datetime import UTC, datetime, timedelta

import fakeredis

from medwatch.bus import Bus
from medwatch.config import load_yaml
from medwatch.contracts import Evidence, Modality, Severity
from medwatch.fusion.worker import GROUP, STREAMS, FusionWorker

T0 = datetime(2026, 1, 1, 8, tzinfo=UTC)


class FakeDb:
    def __init__(self):
        self.evidence, self.snapshots, self.alerts = [], [], {}

    def insert_evidence(self, ev):
        self.evidence.append(ev)

    def insert_risk_snapshot(self, pid, ts, risk, level, contributions):
        self.snapshots.append((pid, ts, risk, level, contributions))

    def get_patient(self, pid):
        return {"patient_id": pid, "display_name": "Maria Souza"}

    def get_open_alert(self, pid):
        rows = [a for a in self.alerts.values() if a["patient_id"] == pid and a["status"] == "open"]
        return dict(rows[-1]) if rows else None

    def last_closed_alert(self, pid):
        rows = [a for a in self.alerts.values() if a["patient_id"] == pid and a["status"] != "open"]
        return dict(rows[-1]) if rows else None

    def insert_alert(self, a, event_ts):
        row = a.model_dump()
        row.pop("event")
        row["level"] = str(a.level)
        row["event_ts"] = event_ts
        self.alerts[a.alert_id] = row

    def update_alert(self, alert_id, **fields):
        row = self.alerts[alert_id]
        row.update({k: str(v) if k == "level" else v for k, v in fields.items()})
        row["updated_at"] = datetime.now(UTC)
        return dict(row)

    def recent_evidence_all(self, window_minutes):
        return list(self.evidence)


def _ev(typ, score, ts, modality=Modality.vitals, sev=Severity.warning, **payload):
    return Evidence(patient_id="P-0001", modality=modality, type=typ, score=score, severity=sev,
                    ts_start=ts, explanation=f"explicação {typ}", model_name="teste",
                    payload=payload)


def _worker(db=None, min_level="warning", cooldown=15):
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    return FusionWorker(bus, db_module=db or FakeDb(), cfg=load_yaml("fusion"),
                        min_level=min_level, cooldown_minutes=cooldown)


def _published(w):
    return [json.loads(f["data"]) for _, f in w.bus.r.xrange("alerts")]


def _respiratory(w, ts=T0):
    w.handle("evidence", json.loads(_ev("news2_medium", 0.6, ts).model_dump_json()))
    w.handle("evidence", json.loads(
        _ev("respiratory_sound", 0.8, ts, modality=Modality.audio).model_dump_json()))


def test_news2_plus_respiratory_sound_creates_critical_alert():
    w = _worker()
    _respiratory(w)
    assert len(w.db.evidence) == 2 and len(w.db.snapshots) == 2
    assert w.db.snapshots[0][3] == "info" and w.db.snapshots[1][2] == 91.4
    pub = _published(w)
    assert len(pub) == 1
    alert = pub[0]
    assert alert["event"] == "created" and alert["level"] == "critical"
    assert alert["title"].startswith("[CRÍTICO] Maria Souza (P-0001) – ")
    lines = alert["summary"].splitlines()
    assert lines[0] == "Risco 91,4/100."
    assert "Piora respiratória confirmada por sinais vitais e voz" in lines[1]
    assert sum(ln.startswith("• ") for ln in lines) == 2
    assert {str(e.evidence_id) for e in w.db.evidence} == set(alert["evidence_ids"])
    assert len(w.db.alerts) == 1


def test_weaker_third_evidence_does_not_create_new_alert():
    w = _worker()
    _respiratory(w)
    extra = _ev("clinical_entity", 0.5, T0 + timedelta(minutes=1), modality=Modality.text)
    w.process(extra)
    assert len(_published(w)) == 1
    assert len(w.db.alerts) == 1
    row = next(iter(w.db.alerts.values()))
    assert str(extra.evidence_id) in [str(i) for i in row["evidence_ids"]]


def test_isolated_info_evidence_creates_no_alert():
    w = _worker(min_level="warning")
    _, alert = w.process(_ev("news2_medium", 0.6, T0))  # risco 39 → info
    assert alert is None and not w.db.alerts and not _published(w)


def test_escalation_publishes_escalated_event():
    w = _worker()
    _, a1 = w.process(_ev("news2_high", 0.4, T0))  # 0.95*0.4 = 38 → info; piso → critical
    assert a1 is not None and a1.level == "critical"
    w2 = _worker()
    _, first = w2.process(_ev("rx_interaction", 0.8, T0, modality=Modality.prescription))
    assert first.level == "warning"  # 0.6*0.8 = 48
    _, esc = w2.process(_ev("fall_detected", 0.9, T0 + timedelta(minutes=1),
                            modality=Modality.video, sev=Severity.critical))
    assert esc is not None and esc.event == "escalated" and esc.level == "critical"
    assert esc.alert_id == first.alert_id
    assert esc.title.startswith("[CRÍTICO]")
    assert [p["event"] for p in _published(w2)] == ["created", "escalated"]


def test_cooldown_after_closed_alert():
    w = _worker(cooldown=15)
    _, a = w.process(_ev("rx_interaction", 0.8, T0, modality=Modality.prescription))
    w.db.alerts[a.alert_id]["status"] = "acknowledged"
    _, again = w.process(_ev("rx_interaction", 0.8, T0 + timedelta(minutes=5),
                             modality=Modality.prescription))
    assert again is None
    _, later = w.process(_ev("rx_interaction", 0.8, T0 + timedelta(minutes=30),
                             modality=Modality.prescription))
    assert later is not None and later.event == "created"
    assert len(w.db.alerts) == 2


def test_rehydrate_restores_window():
    db = FakeDb()
    db.evidence.append(_ev("news2_medium", 0.6, T0))
    w = _worker(db=db)
    assert w.rehydrate() == 1
    result, alert = w.process(_ev("respiratory_sound", 0.8, T0, modality=Modality.audio))
    assert result.risk == 91.4 and "respiratorio_multimodal" in result.rules_fired
    assert alert is not None and alert.level == "critical"


def test_snapshot_keeps_top_10_contributions():
    w = _worker(min_level="critical")
    types = list(load_yaml("fusion")["weights"])[:12]
    for t in types:
        w.process(_ev(t, 0.5, T0))
    assert len(w.db.snapshots[-1][4]) == 10


def test_consumer_group_constants():
    assert GROUP == "worker-fusion"
    assert STREAMS == ["evidence"]
