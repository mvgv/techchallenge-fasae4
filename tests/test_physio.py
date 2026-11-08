import numpy as np

from medwatch.video.dtw import resample
from medwatch.video.models import Person
from medwatch.video.physio import analyze_physio

CFG = {
    "primary_joint": "knee_left",
    "joints": {"knee_left": [0, 1, 2], "knee_right": [13, 14, 15]},
    "pairs": [["knee_left", "knee_right"]],
    "rep_min_prominence_deg": 20,
    "rep_min_distance_s": 0.8,
    "rom_min_ratio": 0.8,
    "asymmetry_max_deg": 15,
    "dtw_max": 15,
    "trunk_max_deg": 30,
}
THR = {"keypoint_min_conf": 0.5}
FPS = 10.0


def _person(left_deg, right_deg):
    kp = np.zeros((17, 2))
    for (a, b, c), ang in (((0, 1, 2), left_deg), ((13, 14, 15), right_deg)):
        kp[b] = [0, 0]
        kp[a] = [1, 0]
        kp[c] = [np.cos(np.radians(ang)), np.sin(np.radians(ang))]
    kp[5] = kp[6] = [0, 0]
    kp[11] = kp[12] = [0, 10]  # tronco vertical
    return Person(None, (0, 0, 1, 1), kp, np.ones(17))


def _squats(amps_left, amps_right=None, n=20):
    """Cada rep: o ângulo vai de 170 a 170-amp e volta."""
    amps_right = amps_right or amps_left
    people = [_person(120, 120)] + [_person(170, 170)] * 5
    for al, ar in zip(amps_left, amps_right, strict=True):
        for k in range(n):
            f = (1 - np.cos(2 * np.pi * k / n)) / 2
            people.append(_person(170 - al * f, 170 - ar * f))
    people.extend([_person(170, 170)] * 5 + [_person(120, 120)])
    return people


def _run(people, reference=None):
    times = [i / FPS for i in range(len(people))]
    return analyze_physio(people, times, FPS, CFG, reference, THR)


def _of(r, type_):
    return [x for x in r.findings if x["type"] == type_]


def test_series_and_reps():
    r = _run(_squats([80, 80, 80]))
    assert len(r.reps) == 3
    assert not r.findings
    assert set(r.series) == {"knee_left", "knee_right"}


def test_low_rom_vs_reference():
    ref = {"rom": {"knee_left": 80.0, "knee_right": 80.0}}
    r = _run(_squats([80, 80, 40, 80, 80, 80]), ref)
    f = _of(r, "physio_low_rom")
    assert len(f) == 1 and f[0]["rep"] == 3
    assert f[0]["score"] > 0.3
    assert "amplitude" in f[0]["explanation"]


def test_low_rom_without_reference_uses_median():
    r = _run(_squats([80, 80, 80, 40, 80, 80]))
    f = _of(r, "physio_low_rom")
    assert [x["rep"] for x in f] == [4]


def test_low_rom_consolidated_when_majority():
    ref = {"rom": {"knee_left": 80.0, "knee_right": 80.0}}
    r = _run(_squats([40, 40, 80, 80]), ref)
    f = _of(r, "physio_low_rom")
    assert len(f) == 1 and f[0]["rep"] is None and f[0]["payload"]["reps"] == [1, 2]


def test_asymmetry():
    r = _run(_squats([80, 80, 80, 80], [50, 50, 50, 50]))
    f = _of(r, "physio_asymmetry")
    assert len(f) == 1 and len(f[0]["payload"]["reps"]) == 4


def test_no_asymmetry_when_symmetric():
    assert not _of(_run(_squats([80, 80, 80, 80])), "physio_asymmetry")


def test_pattern_deviation_with_reference():
    good = np.array([170 - 80 * (1 - np.cos(2 * np.pi * k / 50)) / 2 for k in range(51)])
    ref = {"mean_curves": {"knee_left": resample(good, 50).tolist()}}
    assert not _of(_run(_squats([80, 80, 80, 80]), ref), "physio_pattern_deviation")
    strict = {**CFG, "dtw_max": 5}
    people = _squats([30, 30, 30, 30])
    times = [i / FPS for i in range(len(people))]
    r = analyze_physio(people, times, FPS, strict, ref, THR)
    assert _of(r, "physio_pattern_deviation")


def test_trunk_compensation():
    people = _squats([80, 80, 80, 80])
    for p in people:
        p.keypoints[5] = p.keypoints[6] = np.array([10.0, 0.0])  # tronco a 45°
    assert _of(_run(people), "physio_trunk_compensation")


def test_no_reps_returns_empty():
    r = _run([_person(170, 170)] * 30)
    assert r.reps == [] and r.findings == []
