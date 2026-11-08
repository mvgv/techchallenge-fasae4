from datetime import UTC, datetime

from medwatch.simulator.synthetic import (
    SCENARIOS,
    demo_timeline,
    generate_patient_timeline,
)

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)


def test_deterministic():
    a = generate_patient_timeline("P-1", START, 120, "normal", 7)
    b = generate_patient_timeline("P-1", START, 120, "normal", 7)
    assert [v.model_dump() for v in a[0]] == [v.model_dump() for v in b[0]]
    c = generate_patient_timeline("P-1", START, 120, "normal", 8)
    assert a[0][5].hr != c[0][5].hr


def test_one_sample_per_minute():
    v, rx, m, _ = generate_patient_timeline("P-1", START, 60, "normal", 1)
    assert len(v) == len(m) == 60 and len(rx) >= 2


def test_respiratory_deterioration():
    v, _, _, labels = generate_patient_timeline("P-1", START, 24 * 60,
                                                "respiratory_deterioration", 3)
    assert v[-1].spo2 < 90 and v[-1].rr > 25 and v[-1].on_oxygen
    assert labels[0]["type"] == "respiratory_deterioration"


def test_normal_spo2():
    for seed in range(5):
        v, _, _, labels = generate_patient_timeline("P-1", START, 24 * 60, "normal", seed)
        ok = sum(1 for o in v if o.spo2 >= 94) / len(v)
        assert ok >= 0.99 and labels == []


def test_all_scenarios_have_labels():
    for sc in SCENARIOS:
        if sc in ("normal", "demo"):
            continue
        _, _, _, labels = generate_patient_timeline("P-1", START, 24 * 60, sc, 2)
        assert labels, sc


def test_sensor_artifact_and_rx():
    v, _, _, _ = generate_patient_timeline("P-1", START, 24 * 60, "sensor_artifact", 2)
    assert any(o.spo2 == 0 for o in v) and any(o.hr == 400 for o in v)
    _, rx, _, labels = generate_patient_timeline("P-1", START, 24 * 60, "rx_risky", 2)
    assert {"heparina", "cetorolaco"} <= {e.drug for e in rx}
    assert {lb["type"] for lb in labels} == {"rx_interaction", "rx_dose_change"}


def test_demo():
    start = datetime(2025, 12, 31, 19, 0, tzinfo=UTC)
    v, _, _, labels = demo_timeline("P-0001", start, 1)
    assert len(v) == 480 and v[-1].spo2 < 90 and labels
    _, rx, _, labels = demo_timeline("P-0004", start, 1)
    assert any(e.drug == "morfina" for e in rx)
    assert labels[0]["type"] == "night_agitation"
