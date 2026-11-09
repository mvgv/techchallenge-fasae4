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


def _cfg(persistence, ipers=1):
    from medwatch.config import load_yaml
    cfg = load_yaml("thresholds")
    cfg["vitals"]["zscore"]["persistence"] = persistence
    cfg["vitals"]["zscore"]["cooldown_minutes"] = 0
    cfg["vitals"]["iforest"]["persistence"] = ipers
    cfg["vitals"]["iforest"]["cooldown_minutes"] = 0
    return cfg


def _hr_series(values):
    from datetime import timedelta

    from medwatch.contracts import VitalObservation
    return [VitalObservation(patient_id="P-9", ts=T0 + timedelta(minutes=i), hr=v,
                             spo2=97, rr=15, sbp=120, dbp=75, temp=36.7)
            for i, v in enumerate(values)]


def _z_events(cfg, values):
    w = AnomalyWorker(None, db_module=FakeDb(), cfg=cfg)  # type: ignore[arg-type]
    return [e for v in _hr_series(values) for e in w.process_vital(v)
            if e.type == "vital_zscore" and e.payload["vital"] == "hr"]


def test_zscore_persistence():
    from datetime import timedelta
    base = [75.0 + (i % 2) for i in range(40)]
    spike = base + [150.0] + base[:5]
    assert _z_events(_cfg(1), spike)
    assert not _z_events(_cfg(3), spike)
    evs = _z_events(_cfg(3), base + [90.0, 110.0, 140.0])
    assert evs and evs[0].ts_start == T0 + timedelta(minutes=42)


def test_iforest_persistence():
    class Fake:
        enabled = True
        carry_forward = False

        def __init__(self):
            self.n = 0

        def score(self, feats, key="threshold"):
            self.n += 1
            return (6 <= self.n <= 7) or (9 <= self.n <= 11), 0.9

    def run(ipers):
        w = AnomalyWorker(None, db_module=FakeDb(), iforest=Fake(),  # type: ignore[arg-type]
                          cfg=_cfg(1, ipers))
        return [e for v in _hr_series([75.0] * 30) for e in w.process_vital(v)
                if e.type == "vital_iforest"]
    assert len(run(1)) >= 1
    assert len(run(3)) == 1


def test_iforest_per_model_override():
    class Fake:
        enabled = True
        carry_forward = False
        name = "vitals_iforest_mimic"

        def __init__(self):
            self.keys = []
            self.n = 0

        def score(self, feats, key="threshold"):
            self.keys.append(key)
            self.n += 1
            return 6 <= self.n <= 7, 0.9

    cfg = _cfg(1, 3)
    cfg["vitals"]["iforest"]["per_model"] = {
        "vitals_iforest_mimic": {"threshold_key": "p01", "persistence": 1}}
    fake = Fake()
    w = AnomalyWorker(None, db_module=FakeDb(), iforest=fake, cfg=cfg)  # type: ignore[arg-type]
    evs = [e for v in _hr_series([75.0] * 30) for e in w.process_vital(v)
           if e.type == "vital_iforest"]
    assert len(evs) == 2 and set(fake.keys) == {"p01"}
    fake2 = Fake()
    fake2.name = "vitals_iforest"
    w2 = AnomalyWorker(None, db_module=FakeDb(), iforest=fake2, cfg=cfg)  # type: ignore[arg-type]
    assert not [e for v in _hr_series([75.0] * 30) for e in w2.process_vital(v)
                if e.type == "vital_iforest"]
