import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "evaluate_vitals", Path(__file__).resolve().parents[1] / "scripts" / "evaluate_vitals.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

T0 = datetime(2026, 1, 1, 10, tzinfo=UTC)


def _label(typ, a=0, b=10):
    return {"type": typ, "ts_start": (T0 + timedelta(minutes=a)).isoformat(),
            "ts_end": (T0 + timedelta(minutes=b)).isoformat()}


def test_scenarios_distribution():
    sc = ev._scenarios()
    assert len(sc) == 30 and sc[0][0] == 100 and sc[-1][0] == 129
    assert sum(1 for _, s in sc if s == "normal") == 10


def test_score_tp_fp_fn_and_delay():
    types = {"news2_high"}
    patients = [
        ([_label("hypotension")], [(T0 + timedelta(minutes=5), "news2_high"),
                                   (T0 + timedelta(hours=5), "news2_high")]),
        ([_label("tachy_spike")], []),
        ([_label("sensor_artifact")], [(T0 + timedelta(minutes=1), "news2_high"),
                                       (T0 + timedelta(minutes=2), "vital_zscore")]),
    ]
    m = ev.score_config(patients, types)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 2, 1)
    assert m["median_delay_min"] == 5.0
    assert m["precision"] == 1 / 3
    assert abs(m["fp_per_patient_day"] - 2 / 3) < 1e-9


def test_video_match_tolerance():
    spec = importlib.util.spec_from_file_location(
        "evaluate_video", Path(__file__).resolve().parents[1] / "scripts" / "evaluate_video.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    truth = [dict(type="fall_detected", t_start=10.0, t_end=12.0),
             dict(type="bed_exit", t_start=30.0, t_end=31.0)]
    dets = [dict(type="fall_detected", t_start=13.5, t_end=13.5),
            dict(type="fall_detected", t_start=50.0, t_end=50.0)]
    r = mod.match(truth, dets)
    assert r["fall_detected"] == dict(tp=1, fp=1, fn=0)
    assert r["bed_exit"] == dict(tp=0, fp=0, fn=1)
