import numpy as np

from medwatch.video.dtw import dtw_distance, resample


def test_identity():
    x = np.sin(np.linspace(0, 6, 40))
    assert dtw_distance(x, x) == 0


def test_shifted_closer_than_constant():
    t = np.linspace(0, 4 * np.pi, 60)
    x, y = np.sin(t), np.sin(t + 0.5)
    assert dtw_distance(x, y) < dtw_distance(x, np.zeros(60) + 3)


def test_multidim_and_resample():
    a = np.random.default_rng(0).normal(size=(20, 3))
    assert dtw_distance(a, a) == 0
    assert len(resample(np.arange(7.0), 50)) == 50
