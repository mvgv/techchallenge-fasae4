import numpy as np

from medwatch.video.models import Detection, Person
from medwatch.video.surgery import analyze_surgery

W, H, FPS = 1000, 1000, 10
ZONES = {
    "sterile_field": [[0.30, 0.30], [0.70, 0.30], [0.70, 0.80], [0.30, 0.80]],
    "instrument_tray": [[0.75, 0.55], [0.98, 0.55], [0.98, 0.95], [0.75, 0.95]],
    "max_people_sterile": 3,
    "instrument_classes": ["scissors", "knife"],
}
THR = {"instrument_out_min_s": 5, "count_window_s": 10}
TRAY = (800, 700)
STERILE = (500, 500)
OUTSIDE = (100, 100)


def det(xy, cls="scissors"):
    x, y = xy
    return Detection(cls, 0.9, (x - 10, y - 10, x + 10, y + 10))


def person(xy):
    x, y = xy
    return Person(None, (x - 20, y - 50, x + 20, y + 50), np.zeros((17, 2)), np.ones(17))


def run(dets, people):
    times = [i / FPS for i in range(len(dets))]
    return analyze_surgery(dets, people, times, W, H, ZONES, THR).findings


def types(fs):
    return [f["type"] for f in fs]


def test_intrusion_once_per_episode():
    people = [[person(STERILE)] * 4] * 50 + [[person(STERILE)] * 2] * 30
    fs = run([[det(TRAY)]] * 80, people)
    assert types(fs) == ["surgery_zone_intrusion"]


def test_short_intrusion_ignored():
    people = [[person(STERILE)] * 4] * 10 + [[person(STERILE)]] * 70
    assert run([[det(TRAY)]] * 80, people) == []


def test_instrument_out_of_zone():
    dets = [[det(TRAY)]] * 20 + [[det(TRAY), det(OUTSIDE)]] * 70
    fs = run(dets, [[]] * 90)
    assert types(fs) == ["surgery_instrument_out_of_zone"]


def test_instrument_in_sterile_field_ok():
    assert run([[det(STERILE)]] * 90, [[]] * 90) == []


def test_count_mismatch_critical():
    dets = [[det(TRAY), det(TRAY, "knife")]] * 100 + [[det(TRAY)]] * 100
    fs = run(dets, [[]] * 200)
    assert types(fs) == ["surgery_instrument_count_mismatch"]
    assert fs[0]["score"] == 0.8
    assert fs[0]["severity"] == "critical"


def test_stable_count_no_finding():
    assert run([[det(TRAY)]] * 200, [[]] * 200) == []
