import pytest

pytest.importorskip("pyarrow", exc_type=ImportError)
import pandas as pd  # noqa: E402

from medwatch.simulator.mimic import load_mimic  # noqa: E402


def test_load_mimic(tmp_path):
    ts = pd.Timestamp("2026-01-01T00:00:00Z")
    pd.DataFrame({"patient_id": ["M-1", "M-2"], "ts": [ts, ts], "hr": [80.0, 90.0],
                  "spo2": [97.0, None]}).to_parquet(tmp_path / "vitals.parquet")
    pd.DataFrame({"patient_id": ["M-1"], "ts": [ts], "drug": ["Heparin"], "dose": [5000.0],
                  "unit": ["UNIT"], "route": ["SC"]}).to_parquet(tmp_path / "prescriptions.parquet")
    v, rx = load_mimic(1, tmp_path)
    assert len(v) == 1 and v[0].hr == 80.0 and v[0].sbp is None
    assert rx[0].drug == "Heparin"


def _two_patients(tmp_path):
    t0 = pd.Timestamp("2150-03-01T08:00:00Z")
    t1 = pd.Timestamp("2180-07-01T20:00:00Z")
    pd.DataFrame({
        "patient_id": ["M-1", "M-1", "M-1", "M-2", "M-2"],
        "ts": [t0, t0 + pd.Timedelta(hours=1), t0 + pd.Timedelta(hours=30),
               t1, t1 + pd.Timedelta(minutes=30)],
        "hr": [80.0, 81.0, 82.0, 90.0, 91.0]}).to_parquet(tmp_path / "vitals.parquet")
    pd.DataFrame({"patient_id": ["M-1", "M-1"],
                  "ts": [t0 + pd.Timedelta(minutes=10), t0 - pd.Timedelta(days=400)],
                  "drug": ["Heparin", "Old"], "dose": [1.0, 1.0], "unit": ["U", "U"],
                  "route": ["SC", "PO"]}).to_parquet(tmp_path / "prescriptions.parquet")
    (tmp_path / "splits.yaml").write_text(
        "mimic:\n  calibracao: [M-2]\n  reservado: [M-1]\n", encoding="utf-8")


def test_load_mimic_split_rebase_window(tmp_path):
    from datetime import UTC, datetime
    _two_patients(tmp_path)
    start = datetime(2026, 11, 8, 19, 0, tzinfo=UTC)
    v, rx = load_mimic(None, tmp_path, split="reservado", rebase_start=start,
                       window_hours=24, splits_path=tmp_path / "splits.yaml")
    assert {o.patient_id for o in v} == {"M-1"}
    assert [o.ts for o in v] == [start, start.replace(hour=20)]  # 30 h fica de fora
    assert [e.drug for e in rx] == ["Heparin"]                  # fora da janela: removida
    assert rx[0].ts == start.replace(minute=10)


def test_load_mimic_rebase_each_patient(tmp_path):
    from datetime import UTC, datetime
    _two_patients(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    v, _ = load_mimic(None, tmp_path, rebase_start=start)
    firsts = {}
    for o in v:
        firsts.setdefault(o.patient_id, o.ts)
    assert firsts == {"M-1": start, "M-2": start}


def test_unknown_split(tmp_path):
    _two_patients(tmp_path)
    with pytest.raises(KeyError):
        load_mimic(None, tmp_path, split="validacao", splits_path=tmp_path / "splits.yaml")


def test_replay_mimic_split(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    import fakeredis

    from medwatch.bus import Bus
    from medwatch.config import get_settings
    from medwatch.simulator import mimic, replay
    _two_patients(tmp_path)
    monkeypatch.setattr(mimic, "MIMIC_DIR", tmp_path)
    monkeypatch.setattr(mimic, "load_yaml", lambda name: {"mimic": {"reservado": ["M-1"]}})
    monkeypatch.setattr(get_settings(), "local_storage_dir", tmp_path)
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    start = datetime(2026, 11, 8, 19, 0, tzinfo=UTC)
    n = replay.run("mimic", 5, 60, start, fast=True, bus=bus, mimic_split="reservado",
                   mimic_hours=24)
    assert n == 3 and bus.r.xlen("vitals") == 2 and bus.r.xlen("prescriptions") == 1
    assert bus.r.get("sim:clock") == start.replace(hour=20).isoformat()


def test_missing_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_mimic(1, tmp_path)


def test_prepare_mimic_arterial_and_celsius(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from prepare_mimic import prepare

    (tmp_path / "icu").mkdir()
    (tmp_path / "hosp").mkdir()
    t1, t2 = "2150-01-01 10:00:00", "2150-01-01 11:00:00"
    pd.DataFrame({
        "subject_id": [7, 7, 7, 7, 7, 7],
        "charttime": [t1, t1, t1, t2, t2, t2],
        "itemid": [220045, 220179, 223762, 220050, 220179, 223761],
        "valuenum": [80.0, 120.0, 37.0, 140.0, None, 98.6],
    }).to_csv(tmp_path / "icu" / "chartevents.csv.gz", index=False)
    pd.DataFrame({"subject_id": [7], "starttime": [t1], "drug": ["Heparin"],
                  "dose_val_rx": ["5000"], "dose_unit_rx": ["UNIT"], "route": ["SC"]}
                 ).to_csv(tmp_path / "hosp" / "prescriptions.csv.gz", index=False)
    prepare(tmp_path)
    v = pd.read_parquet(tmp_path / "vitals.parquet").sort_values("ts")
    assert v["patient_id"].tolist() == ["M-7", "M-7"]
    assert v["sbp"].tolist() == [120.0, 140.0]  # arterial preenche a lacuna
    assert v["temp"].round(1).tolist() == [37.0, 37.0]
