from datetime import UTC, datetime

import pytest

from medwatch.anomaly.filters import clean_observation
from medwatch.anomaly.news2 import (
    news2,
    score_hr,
    score_rr,
    score_sbp,
    score_spo2,
    score_temp,
)
from medwatch.config import load_yaml
from medwatch.contracts import VitalObservation


def obs(**kw):
    base = dict(
        patient_id="P-0001",
        ts=datetime(2026, 1, 1, tzinfo=UTC),
        rr=16,
        spo2=98,
        sbp=120,
        hr=70,
        temp=37.0,
    )
    base.update(kw)
    return VitalObservation(**base)


def test_normal():
    r = news2(obs())
    assert r["total"] == 0 and r["band"] == "low"


def test_low_medium():
    r = news2(obs(rr=26))
    assert r["total"] == 3 and r["band"] == "low_medium"


def test_medium():
    r = news2(obs(hr=115, spo2=94, rr=22))
    assert r["total"] == 5 and r["band"] == "medium"


def test_high():
    r = news2(obs(rr=25, spo2=91, sbp=95, hr=115, temp=38.5, on_oxygen=True))
    assert r["total"] == 13 and r["band"] == "high"


def test_missing():
    r = news2(obs(spo2=None))
    assert r["missing"] == ["spo2"] and "spo2" not in r["params"]


@pytest.mark.parametrize(
    "fn,v,exp",
    [
        (score_rr, 8, 3),
        (score_rr, 9, 1),
        (score_rr, 20, 0),
        (score_rr, 21, 2),
        (score_spo2, 96, 0),
        (score_spo2, 95, 1),
        (score_sbp, 111, 0),
        (score_sbp, 110, 1),
        (score_hr, 90, 0),
        (score_hr, 91, 1),
        (score_temp, 38.0, 0),
        (score_temp, 38.1, 1),
    ],
)
def test_boundaries(fn, v, exp):
    assert fn(v) == exp


def test_clean_observation():
    bounds = load_yaml("thresholds")["vitals"]["physiologic_bounds"]
    cleaned, dropped = clean_observation(obs(spo2=0), bounds)
    assert cleaned.spo2 is None and dropped == ["spo2"]
    assert cleaned.hr == 70
