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
