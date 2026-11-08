import math
from datetime import UTC, datetime, timedelta

from medwatch.config import load_yaml
from medwatch.contracts import Evidence
from medwatch.fusion.engine import FusionEngine

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def ev(type_, score, modality="vitals", ts=T0, **payload):
    return Evidence(
        patient_id="P-0001", modality=modality, type=type_, score=score,
        severity="info", ts_start=ts, explanation="x", model_name="t", payload=payload,
    )


def engine():
    return FusionEngine(load_yaml("fusion"))


def test_single_news2_medium():
    r = engine().add(ev("news2_medium", 0.6))
    assert r.risk == 39.0
    assert r.level == "info"


def test_repeated_same_type_counts_once():
    e = engine()
    for _ in range(5):
        r = e.add(ev("news2_medium", 0.6))
    assert r.risk == 39.0
    assert len(r.contributions) == 1


def test_respiratory_rule():
    e = engine()
    e.add(ev("news2_medium", 0.6))
    r = e.add(ev("respiratory_sound", 0.8, modality="audio"))
    assert r.rules_fired == ["respiratorio_multimodal"]
    assert r.risk == 91.4
    assert r.level == "critical"


def test_decay():
    e = engine()
    e.add(ev("vital_zscore", 1.0, vital="hr", ts=T0))
    r = e.compute("P-0001", T0 + timedelta(minutes=30))
    assert math.isclose(r.contributions[0]["contrib"], 0.4 * math.exp(-2), abs_tol=1e-4)


def test_floor_critical():
    r = engine().add(ev("fall_detected", 0.5, modality="video"))
    assert r.level == "critical"
    assert r.risk >= 70
    assert r.floor_applied


def test_old_evidence_discarded():
    e = engine()
    e.add(ev("news2_medium", 0.6, ts=T0))
    e.add(ev("vital_zscore", 0.5, ts=T0 + timedelta(minutes=361)))
    assert [x.type for x in e.windows["P-0001"]] == ["vital_zscore"]


def test_rule_payload_must_match():
    e = engine()
    e.add(ev("vital_zscore", 0.9, vital="hr"))
    r = e.add(ev("respiratory_sound", 0.8, modality="audio"))
    assert r.rules_fired == []
