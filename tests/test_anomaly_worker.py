import json
from datetime import UTC, datetime

import fakeredis

from medwatch.anomaly.worker import GROUP, STREAMS, AnomalyWorker
from medwatch.bus import Bus
from medwatch.simulator.synthetic import generate_patient_timeline

T0 = datetime(2026, 1, 1, 8, tzinfo=UTC)


class FakeDb:
    def __init__(self):
        self.vitals, self.rx, self.moves = [], [], []

    def insert_vital(self, obs, total):
        self.vitals.append((obs, total))

    def insert_prescription(self, ev, drug_norm):
        self.rx.append((ev, drug_norm))

    def insert_movement(self, s):
        self.moves.append(s)


def _run(scenario, seed=1, minutes=1440):
    vitals, rx, moves, _ = generate_patient_timeline("P-0001", T0, minutes, scenario, seed=seed)
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    db = FakeDb()
    worker = AnomalyWorker(bus, db_module=db)
    events = ([(v.ts, "vitals", v) for v in vitals] + [(e.ts, "prescriptions", e) for e in rx]
              + [(m.ts, "movement", m) for m in moves])
    events.sort(key=lambda x: x[0])
    for _, stream, model in events:
        worker.handle(stream, json.loads(model.model_dump_json()))
    published = [json.loads(f["data"]) for _, f in bus.r.xrange("evidence")]
    return published, db, len(vitals)


def test_respiratory_deterioration_news2():
    evs, db, n = _run("respiratory_deterioration")
    types = [e["type"] for e in evs]
    assert "news2_medium" in types and "news2_high" in types
    assert types.index("news2_medium") < types.index("news2_high")
    assert len(db.vitals) == n
    high = next(e for e in evs if e["type"] == "news2_high")
    assert high["severity"] == "critical"
    assert high["explanation"].startswith("NEWS2 = ")
    assert high["source_ref"].startswith("vitals:P-0001@")


def test_sensor_artifact_no_news_nor_zscore():
    evs, _, _ = _run("sensor_artifact")
    assert not [e for e in evs if e["type"].startswith("news2_")]
    # z-scores do ruído natural podem ocorrer; nenhum pode vir dos pontos inválidos
    bad = [e for e in evs if e["type"] == "vital_zscore"
           and e["payload"]["value"] in (0, 400)]
    assert not bad


def test_movement_and_rx_events_are_published():
    evs, db, _ = _run("night_agitation")
    assert db.moves
    assert any(e["type"] == "movement_night_agitation" for e in evs)
    evs, db, _ = _run("rx_risky")
    assert db.rx
    assert any(e["type"].startswith("rx_") for e in evs)


def test_consumer_group_constants():
    assert GROUP == "worker-anomaly"
    assert STREAMS == ["vitals", "prescriptions", "movement"]
