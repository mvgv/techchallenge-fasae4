import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from evaluate_fall_v2 import T37_DEFAULTS, choose, diagnose, grid_combos  # noqa: E402

from medwatch.video.models import Person  # noqa: E402

H = 480
THR = {"keypoint_min_conf": 0.5,
       "fall": {"window_s": 1.0, "hip_drop_min": 0.15, "lying_aspect_min": 1.3,
                "lying_min_s": 0.5}}


def _person(hip_y: float, w: float, h: float, hips: bool = True) -> Person:
    kp = np.zeros((17, 2))
    kp[11] = kp[12] = (300, hip_y * H)
    conf = np.full(17, 0.9)
    if not hips:
        conf[[11, 12]] = 0.1
    return Person(1, (300 - w / 2, hip_y * H - h / 2, 300 + w / 2, hip_y * H + h / 2), kp, conf)


def _data(frames):
    return {"people": frames, "times": [k * 0.125 for k in range(len(frames))], "w": 640, "h": H}


def test_small_drop_is_cause_c():
    frames = [_person(0.57, 80, 220)] * 10 + [_person(0.62, 200, 80)] * 10
    d = diagnose(_data(frames), (1.2, 2.4), THR)
    assert d["gate"] == "c"
    assert abs(d["drop"] - 0.05) < 1e-6


def test_tall_box_after_fall_is_cause_d():
    frames = [_person(0.5, 80, 220)] * 10 + [_person(0.8, 80, 120)] * 10
    assert diagnose(_data(frames), (1.2, 2.4), THR)["gate"] == "d"


def test_short_lying_is_cause_e_and_missing_pose_counted():
    frames = [_person(0.5, 80, 220)] * 10 + [_person(0.8, 200, 80)] * 3 + [None] * 4
    d = diagnose(_data(frames), (1.2, 2.0), THR)
    assert d["gate"] == "e"
    assert d["lying_s"] < 0.5
    assert d["pose_after"] < 1.0


def test_no_hips_is_cause_b_and_no_person_is_a():
    frames = [_person(0.5, 80, 220, hips=False)] * 20
    assert diagnose(_data(frames), (1.2, 2.4), THR)["gate"] == "b"
    assert diagnose(_data([None] * 20), (1.2, 2.4), THR)["gate"] == "a"


def _g(f1, adl_fp, **opts):
    return {**T37_DEFAULTS, "f1": f1, "adl_fp": adl_fp, "precision": 1.0, "lying_min_s": 0.5,
            "hip_drop_min": 0.15, **opts}


def test_choose_respects_adl_limit_and_prefers_simpler_rule():
    grid = [_g(0.95, 3, hip_from_box=True), _g(0.9, 1, hip_from_box=True, end_closes_lying=True),
            _g(0.9, 0, hip_from_box=True)]
    best = choose(grid)
    assert best["adl_fp"] <= 1 and best["f1"] == 0.9
    assert best["end_closes_lying"] is False   # empate: menos opções novas ligadas


def test_grid_has_both_drop_units():
    combos = grid_combos()
    assert {c["drop_norm"] for c in combos} == {"frame", "person"}
    assert len(combos) == len({tuple(sorted(c.items(), key=str)) for c in combos})
