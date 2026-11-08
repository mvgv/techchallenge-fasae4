from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from medwatch.config import get_settings, load_yaml
from medwatch.contracts import Evidence, Modality, Severity
from medwatch.timeutil import parse_ts, to_iso, utcnow


def _evidence(**kw) -> Evidence:
    base = {
        "patient_id": "P-0001",
        "modality": Modality.vitals,
        "type": "news2_high",
        "score": 0.8,
        "severity": Severity.warning,
        "ts_start": datetime(2026, 1, 1, tzinfo=UTC),
        "explanation": "NEWS2 elevado",
        "model_name": "news2",
    }
    base.update(kw)
    return Evidence(**base)


def test_evidence_valid_and_roundtrip():
    ev = _evidence()
    assert Evidence.model_validate_json(ev.model_dump_json()) == ev


def test_evidence_score_out_of_range():
    with pytest.raises(ValidationError):
        _evidence(score=1.5)


def test_load_yaml(monkeypatch):
    config_dir = Path(__file__).resolve().parents[1] / "config"
    monkeypatch.setenv("CONFIG_DIR", str(config_dir))
    get_settings.cache_clear()
    load_yaml.cache_clear()
    try:
        assert load_yaml("thresholds")["vitals"]["zscore"]["threshold"] == 3.0
    finally:
        get_settings.cache_clear()
        load_yaml.cache_clear()


def test_timeutil():
    assert utcnow().tzinfo is not None
    assert parse_ts("2026-01-01T10:00:00Z") == datetime(2026, 1, 1, 10, tzinfo=UTC)
    assert parse_ts("2026-01-01T10:00:00") == datetime(2026, 1, 1, 10, tzinfo=UTC)
    brt = parse_ts("2026-01-01T10:00:00-03:00")
    assert brt == datetime(2026, 1, 1, 13, tzinfo=UTC)
    assert brt.utcoffset() == timedelta(0)
    local = datetime(2026, 1, 1, 10, tzinfo=timezone(timedelta(hours=-3)))
    assert to_iso(local) == "2026-01-01T13:00:00+00:00"
