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


def test_fall_tolerates_pose_gaps_while_lying():
    frames = [person((OUT_X, 0.4 * H), 60, 200)] * 20
    for k in range(1, 6):
        frames.append(person((OUT_X, (0.4 + 0.08 * k) * H), 100, 150))
    # deitado, com a pose falhando em parte dos quadros (pessoa None)
    lying = person((OUT_X, 0.8 * H), 200, 60)
    frames += [lying, None, None, lying, None, lying] * 8
    res = analyze_bed(frames, times(len(frames)), W, H, {"bed": BED}, THR)
    assert len([f for f in res.findings if f["type"] == "fall_detected"]) == 1


def _thr(**fall):
    return {**THR, "fall": {**THR["fall"], "hip_drop_min": 0.15, "lying_min_s": 0.5, **fall}}


def _fall_toward_camera(lying_box=(80, 70)):
    """Queda de frente: o quadril desce pouco na imagem e a caixa fica alta e estreita."""
    frames = [person((OUT_X, 0.57 * H), 80, 220)] * 20
    for k in range(1, 5):
        frames.append(person((OUT_X, (0.57 + 0.05 * k) * H), 80, 220 - 30 * k))
    frames += [person((OUT_X, 0.80 * H), *lying_box)] * 20
    return frames


def test_height_ratio_accepts_fall_toward_camera():
    frames = _fall_toward_camera()
    t = times(len(frames))
    assert analyze_bed(frames, t, W, H, {}, _thr()).findings == []
    res = analyze_bed(frames, t, W, H, {}, _thr(lying_height_ratio=0.6))
    assert [f["type"] for f in res.findings] == ["fall_detected"]


def test_drop_normalized_by_person_height():
    # pessoa pequena (longe): o quadril desce 10% do quadro, mas 40% da altura dela
    frames = [person((OUT_X, 0.5 * H), 30, 0.25 * H)] * 20
    frames += [person((OUT_X, 0.6 * H), 0.25 * H, 30)] * 20
    t = times(len(frames))
    assert analyze_bed(frames, t, W, H, {}, _thr()).findings == []
    res = analyze_bed(frames, t, W, H, {}, _thr(drop_norm="person", hip_drop_min=0.3))
    assert len(res.findings) == 1
    assert "da pessoa" in res.findings[0]["explanation"]


def test_hip_from_box_when_hips_missing():
    frames = [person((OUT_X, 0.4 * H), 60, 200)] * 20
    no_hips = person((OUT_X, 0.8 * H), 200, 60)
    no_hips.kp_conf[[11, 12]] = 0.0
    frames += [no_hips] * 20
    t = times(len(frames))
    assert analyze_bed(frames, t, W, H, {}, _thr()).findings == []
    assert len(analyze_bed(frames, t, W, H, {}, _thr(hip_from_box=True)).findings) == 1


def test_end_of_video_closes_lying_phase():
    frames = [person((OUT_X, 0.4 * H), 60, 200)] * 20
    frames += [person((OUT_X, 0.8 * H), 200, 60)] * 11 + [None] * 3   # deitado ~0,1 s e some
    t = times(len(frames))
    assert analyze_bed(frames, t, W, H, {}, _thr(lying_min_s=2.0)).findings == []
    res = analyze_bed(frames, t, W, H, {}, _thr(lying_min_s=2.0, end_closes_lying=True))
    assert len(res.findings) == 1
    assert res.findings[0]["t_end"] == t[-1]
    # se a pessoa se levanta antes do fim, o fim do vídeo não fecha a fase deitada
    up = frames + [person((OUT_X, 0.4 * H), 60, 200)] * 5
    assert analyze_bed(up, times(len(up)), W, H, {},
                       _thr(lying_min_s=2.0, end_closes_lying=True)).findings == []


def test_skip_missing_j_uses_next_frame_with_hip():
    frames = [person((OUT_X, 0.4 * H), 60, 200)] * 20 + [None] * 3
    frames += [person((OUT_X, 0.8 * H), 200, 60)] * 20
    t = times(len(frames))
    thr = _thr(window_s=0.2)
    assert analyze_bed(frames, t, W, H, {}, thr).findings == []
    assert len(analyze_bed(frames, t, W, H, {}, _thr(window_s=0.2, skip_missing_j=True))
               .findings) == 1


def test_fallback_person_from_detector():
    from medwatch.video.models import Detection, fallback_person

    dets = [Detection("person", 0.3, (0, 0, 10, 10)), Detection("person", 0.2, (0, 0, 50, 50)),
            Detection("chair", 0.9, (0, 0, 99, 99))]
    p = fallback_person(dets, 0.25)
    assert p.xyxy == (0.0, 0.0, 10.0, 10.0) and not p.kp_conf.any()
    assert fallback_person(dets, 0.5) is None


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
