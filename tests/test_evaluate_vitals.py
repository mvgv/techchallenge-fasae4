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


def test_episodes_merge_repeats_and_report_normals():
    types = {"news2_high"}
    rep = [(T0 + timedelta(minutes=100 + 10 * i), "news2_high") for i in range(5)]
    patients = [
        ([_label("hypotension", 0, 10)], [(T0 + timedelta(minutes=5), "news2_high")] + rep),
        ([], rep + [(T0 + timedelta(hours=8), "news2_high")]),
    ]
    m = ev.score_episodes(patients, types)
    # repetições a cada 10 min formam 1 episódio; o de 8 h é outro
    assert (m["tp"], m["fn"], m["fp"]) == (1, 0, 3)
    assert m["fp_normal"] == 2 and m["fp_normal_per_day"] == 2.0


def _evidence(minute, typ="news2_high", score=1.0):
    from medwatch.contracts import Evidence, Modality, Severity
    return Evidence(patient_id="P", modality=Modality.vitals, type=typ, score=score,
                    severity=Severity.warning, ts_start=T0 + timedelta(minutes=minute),
                    explanation="x", model_name="m", payload={}, source_ref="r")


def test_alerts_open_and_close():
    from medwatch.config import load_yaml
    cfg = load_yaml("fusion")
    # duas rajadas separadas por 5 h: risco cai abaixo de 20 por 60 min entre elas
    opens = ev.alerts_from_evidence([_evidence(0), _evidence(5), _evidence(300)], cfg)
    assert opens == [T0, T0 + timedelta(minutes=300)]
    # evidência fraca (risco < 40) não abre alerta
    assert ev.alerts_from_evidence([_evidence(0, "vital_zscore", 0.5)], cfg) == []
    # rajada contínua dentro do mesmo alerta: abre uma vez só
    assert len(ev.alerts_from_evidence([_evidence(m) for m in range(0, 120, 10)], cfg)) == 1


def test_score_alerts_tp_fp_and_normal():
    from medwatch.config import load_yaml
    cfg = load_yaml("fusion")
    pos = ([_label("hypotension", 0, 10)], [_evidence(5)])
    normal = ([], [_evidence(30)])
    m = ev.score_alerts([pos, normal], cfg)
    assert (m["tp"], m["fp"], m["fn"]) == (1, 1, 0)
    assert m["fp_normal_per_day"] == 1.0 and m["median_delay_min"] == 5.0
