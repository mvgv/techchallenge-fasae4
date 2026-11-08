import numpy as np

from medwatch.video.bed import analyze_bed
from medwatch.video.models import Person

W, H = 640, 480
FPS = 10
THR = {
    "keypoint_min_conf": 0.5,
    "fall": {"window_s": 1.0, "hip_drop_min": 0.25, "lying_aspect_min": 1.3, "lying_min_s": 2.0},
    "inactivity_motion_max": 0.01,
}
BED = [[0.20, 0.35], [0.80, 0.35], [0.80, 0.95], [0.20, 0.95]]
OUT_X = 0.05 * W  # fora do leito
IN_X = 0.5 * W


def person(hip_xy, bbox_w, bbox_h, jitter=0.0):
    kp = np.tile(np.array(hip_xy, dtype=float), (17, 1)) + jitter
    cx, cy = hip_xy
    box = (cx - bbox_w / 2, cy - bbox_h / 2, cx + bbox_w / 2, cy + bbox_h / 2)
    return Person(None, box, kp, np.ones(17))


def times(n):
    return [i / FPS for i in range(n)]


def test_fall_detected():
    frames = [person((OUT_X, 0.4 * H), 60, 200)] * 20
    # queda: quadril desce 40% da altura em 0,5 s
    for k in range(1, 6):
        frames.append(person((OUT_X, (0.4 + 0.08 * k) * H), 100, 150))
    frames += [person((OUT_X, 0.8 * H), 200, 60)] * 40
    res = analyze_bed(frames, times(len(frames)), W, H, {"bed": BED}, THR)
    falls = [f for f in res.findings if f["type"] == "fall_detected"]
    assert len(falls) == 1
    assert falls[0]["score"] == 0.9
    assert 0 <= falls[0]["frame_index"] < len(frames)


def test_still_person_no_fall():
    frames = [person((OUT_X, 0.4 * H), 60, 200)] * 60
    res = analyze_bed(frames, times(60), W, H, {"bed": BED}, THR)
    assert res.findings == []


def test_bed_exit():
    frames = [person((IN_X, 0.6 * H), 200, 60)] * 40 + [person((OUT_X, 0.6 * H), 60, 200)] * 40
    res = analyze_bed(frames, times(80), W, H, {"bed": BED}, THR)
    exits = [f for f in res.findings if f["type"] == "bed_exit_video"]
    assert len(exits) == 1
    assert abs(exits[0]["t_start"] - 4.0) < 0.2


def test_activity_and_no_person():
    still = [person((IN_X, 0.6 * H), 200, 60)] * 30
    moving = [person((IN_X, 0.6 * H), 200, 60, jitter=(k % 2) * 6.0) for k in range(30)]
    res = analyze_bed(still + moving, times(60), W, H, {"bed": BED}, THR)
    assert len(res.activity_per_minute) == 1
    t0, act, in_bed = res.activity_per_minute[0]
    assert t0 == 0 and act > 0 and in_bed is True
    res2 = analyze_bed(still, times(30), W, H, {"bed": BED}, THR)
    assert res2.activity_per_minute[0][1] == 0.0

    none = analyze_bed([None] * 20, times(20), W, H, {"bed": BED}, THR)
    assert none.activity_per_minute == [(0.0, 0.0, None)]
    assert none.findings == []
