import numpy as np

from medwatch.video.reps import segment_reps


def test_sine_five_cycles():
    fps = 10
    t = np.arange(0, 55, 1 / fps)
    x = 120 + 50 * np.sin(2 * np.pi * t / 10 + np.pi / 2)
    assert len(segment_reps(x, fps, 20, 0.8)) in (4, 5)


def test_inverted_series():
    fps = 10
    t = np.arange(0, 50, 1 / fps)
    x = 50 + 50 * np.sin(2 * np.pi * t / 10 - np.pi / 2)
    assert len(segment_reps(x, fps, 20, 0.8)) >= 3


def test_flat_has_no_reps():
    assert segment_reps(np.full(100, 90.0), 10, 20, 0.8) == []
