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
