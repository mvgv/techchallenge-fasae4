from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from medwatch.anomaly.iforest import (
    VitalsIForest,
    build_features,
    features_from_series,
    train_and_save,
)
from medwatch.contracts import VitalObservation
from medwatch.simulator.synthetic import generate_patient_timeline

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _obs(i: int, **kw) -> VitalObservation:
    base = dict(hr=75, sbp=120, dbp=75, spo2=98, rr=15, temp=36.7)
    base.update(kw)
    return VitalObservation(patient_id="P", ts=T0 + timedelta(minutes=i), **base)


@pytest.fixture(scope="module")
def model(tmp_path_factory):
    d = tmp_path_factory.mktemp("models")
    rows = []
    for seed in range(1, 6):
        vitals, *_ = generate_patient_timeline(f"T{seed}", T0, 24 * 60, "normal", seed)
        rows += features_from_series(vitals)
    train_and_save(np.vstack(rows), d)
    m = VitalsIForest(d)
    assert m.load()
    return m, np.vstack(rows)


def test_build_features_shape_and_deltas():
    hist = [_obs(i) for i in range(5)] + [_obs(5, hr=95)]
    f = build_features(hist)
    assert f.shape == (10,)
    assert f[0] == 95 and f[6] == pytest.approx(20)


def test_build_features_none_cases():
    assert build_features([_obs(i) for i in range(5)]) is None
    assert build_features([_obs(i) for i in range(5)] + [_obs(5, spo2=None)]) is None


def test_anomaly_detected(model):
    m, X = model
    bad = build_features([_obs(i) for i in range(5)] + [_obs(5, hr=160, spo2=85)])
    anom, score = m.score(bad)
    assert anom and score > 0.5
    anom, score = m.score(np.median(X, axis=0))
    assert not anom and score < 0.5


def test_disabled_without_model(tmp_path):
    m = VitalsIForest(tmp_path)
    assert not m.load()
    assert m.score(np.zeros(10)) == (False, 0.0)


def test_build_features_carry_forward():
    hist = [_obs(i) for i in range(5)] + [_obs(5, temp=None, hr=95)]
    assert build_features(hist) is None
    f = build_features(hist, carry_forward=True)
    assert f[5] == pytest.approx(36.7) and f[0] == 95


def test_named_model_and_val_thresholds(tmp_path, model):
    _, X = model
    meta = train_and_save(X[:500], tmp_path, "vitals_iforest_mimic", X_val=X[500:900],
                          extra_meta={"carry_forward": True})
    assert "train_percentiles" in meta and meta["n_val_samples"] == 400
    m = VitalsIForest(tmp_path, "vitals_iforest_mimic")
    assert m.load() and m.carry_forward
    assert not VitalsIForest(tmp_path, "vitals_iforest").load()


def test_resolve_out(tmp_path):
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from train_vitals_iforest import resolve_out
    assert resolve_out(tmp_path / "vitals_iforest_mimic", "x") == (tmp_path, "vitals_iforest_mimic")
    assert resolve_out(tmp_path, "vitals_iforest") == (tmp_path, "vitals_iforest")
