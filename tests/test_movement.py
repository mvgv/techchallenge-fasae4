from datetime import UTC, datetime

from medwatch.anomaly.movement import MovementMonitor
from medwatch.config import load_yaml
from medwatch.contracts import MovementSample
from medwatch.simulator.synthetic import generate_patient_timeline

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _types(scenario, minutes=1440, seed=1):
    _, _, moves, _ = generate_patient_timeline("P", T0, minutes, scenario, seed=seed)
    mon = MovementMonitor(load_yaml("thresholds")["movement"])
    return [e.type for m in moves for e in mon.process(m)]


def test_inactivity():
    assert _types("inactivity").count("movement_inactivity") == 1


def test_night_agitation_and_bed_exit():
    types = _types("night_agitation")
    assert "movement_night_agitation" in types
    assert "movement_bed_exit" in types


def test_normal_is_silent():
    assert _types("normal") == []


def test_night_wraps_midnight():
    mon = MovementMonitor(load_yaml("thresholds")["movement"])
    assert mon.is_night(23) and mon.is_night(2) and not mon.is_night(6) and not mon.is_night(12)


def test_bed_exit_only_at_night():
    mon = MovementMonitor(load_yaml("thresholds")["movement"])
    day = datetime(2026, 1, 1, 12, tzinfo=UTC)
    for i, bed in enumerate([True, False]):
        s = MovementSample(patient_id="P", ts=day.replace(minute=i), activity_count=20,
                           in_bed=bed, source="sensor")
        assert mon.process(s) == []
