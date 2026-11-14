import math

import numpy as np

from medwatch.video.models import Person
from medwatch.video.physio_features import feature_names, feature_vector, to_matrix

CFG = {
    "primary_joint": "knee_left",
    "joints": {"knee_left": [11, 13, 15], "knee_right": [12, 14, 16]},
    "pairs": [["knee_left", "knee_right"]],
    "rep_min_prominence_deg": 20,
    "rep_min_distance_s": 0.8,
}


def _person(knee_deg_left: float, knee_deg_right: float, lean_px: float = 0.0,
            shoulder_w: float = 40.0) -> Person:
    kp = np.zeros((17, 2))
    kp[11], kp[12] = (100, 200), (140, 200)            # quadris (40 px de largura)
    kp[5] = (120 - shoulder_w / 2 + lean_px, 100)       # ombros
    kp[6] = (120 + shoulder_w / 2 + lean_px, 100)
    for hip, knee, ank, deg in ((11, 13, 15, knee_deg_left), (12, 14, 16, knee_deg_right)):
        kp[knee] = kp[hip] + (0, 60)
        a = math.radians(180 - deg)
        kp[ank] = kp[knee] + (60 * math.sin(a), 60 * math.cos(a))
    kp[7], kp[9] = kp[5] + (0, 50), kp[5] + (0, 100)    # cotovelo esquerdo esticado
    kp[8], kp[10] = kp[6] + (0, 50), kp[6] + (30, 70)
    return Person(None, (0, 0, 1, 1), kp, np.ones(17))


def _rep(n=30, rom_l=90, rom_r=90, lean=0.0):
    ph = np.sin(np.linspace(0, np.pi, n))
    people = [_person(180 - rom_l * s, 180 - rom_r * s, lean * s) for s in ph]
    return people, [k / 10 for k in range(n)]


def test_amplitude_asymmetry_curve_and_duration():
    people, t = _rep(rom_l=90, rom_r=60)
    f = feature_vector(people, t, CFG)
    assert set(f) == set(feature_names(CFG))
    assert abs(f["rom_knee_left"] - 90) < 6 and abs(f["rom_knee_right"] - 60) < 6
    assert abs(f["asym_knee_left_knee_right"] - 30) < 8
    assert f["duration_s"] == t[-1] and f["missing_frac"] == 0.0
    assert f["curve_00"] > 170 and min(f[f"curve_{k:02d}"] for k in range(20)) < 100
    assert math.isnan(f["dtw_knee_left"])   # sem referência


def test_dtw_zero_against_own_curve_and_trunk_lean():
    from medwatch.video.dtw import resample
    from medwatch.video.physio_features import _series

    people, t = _rep(lean=30)
    s = _series(people, CFG["joints"], 0.5)
    ref = {"mean_curves": {j: resample(v, 50).tolist() for j, v in s.items()}}
    f = feature_vector(people, t, CFG, ref)
    assert f["dtw_knee_left"] < 1e-6
    assert f["trunk_max"] > 10 and f["trunk_min"] < 1
    assert abs(f["width_ratio_min"] - 1.0) < 1e-6
    assert f["elbow_min"] < 180


def test_missing_pose_gives_nan_and_fraction():
    people, t = _rep()
    people = [None] * 10 + people[10:]
    f = feature_vector(people, t, CFG)
    assert abs(f["missing_frac"] - 10 / 30) < 1e-9
    empty = feature_vector([None] * 5, [0, 0.1, 0.2, 0.3, 0.4], CFG)
    assert empty["missing_frac"] == 1.0 and math.isnan(empty["rom_knee_left"])
    m = to_matrix([f, empty], feature_names(CFG))
    assert m.shape == (2, len(feature_names(CFG))) and np.isnan(m[1]).any()


def test_counts_repetitions_over_recording():
    people = []
    for _ in range(4):
        people += _rep()[0]
    t = [k / 10 for k in range(len(people))]
    # topo a topo: as repetições das pontas não fecham um ciclo completo
    assert feature_vector(people, t, CFG)["n_reps"] >= 2
