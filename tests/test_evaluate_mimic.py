import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

from medwatch.config import load_yaml
from medwatch.contracts import PrescriptionEvent, VitalObservation

_spec = importlib.util.spec_from_file_location(
    "evaluate_mimic", Path(__file__).resolve().parents[1] / "scripts" / "evaluate_mimic.py")
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)

T0 = datetime(2150, 1, 1, 8, tzinfo=UTC)


def _v(h: float, **kw) -> VitalObservation:
    base = dict(hr=80.0, sbp=120.0, dbp=70.0, spo2=97.0, rr=16.0, temp=36.8)
    base.update(kw)
    return VitalObservation(patient_id="M-1", ts=T0 + timedelta(hours=h), **base)


def test_segments_split_on_gap_and_assign_rx():
    vit = [_v(0), _v(1), _v(2), _v(40), _v(41)]
    rx = [PrescriptionEvent(rx_id=f"r{i}", patient_id="M-1", ts=T0 + timedelta(hours=h),
                            drug="x", action="start") for i, h in enumerate((-2, 30, 41, 100))]
    segs = em.segments(vit, rx)
    assert [len(s) for s, _ in segs] == [3, 2]
    assert [e.rx_id for e in segs[0][1]] == ["r0"]
    assert [e.rx_id for e in segs[1][1]] == ["r1", "r2"]
    assert em.stay_days(segs[0][0]) == 2 / 24
    assert em.stay_days([_v(0)]) == 1 / 24


def test_run_stay_news2_alert_level():
    vit = [_v(h) for h in range(10)] + [_v(10 + h, spo2=86.0, rr=30.0, hr=125.0, sbp=88.0)
                                        for h in range(3)]
    evs = em.run_stay(vit, [], None, load_yaml("thresholds"))
    assert any(e.type == "news2_high" for e in evs)
    alerts = em.ev.alert_details(evs, load_yaml("fusion"))
    assert len(alerts) == 1 and alerts[0]["level"] == "critical"
    assert alerts[0]["opened"] == T0 + timedelta(hours=10)
    assert "news2_high" in alerts[0]["types"]
