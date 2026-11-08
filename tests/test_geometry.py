import numpy as np

from medwatch.video.geometry import angle_series, joint_angle, point_in_zone, trunk_angle
from medwatch.video.models import Person


def test_right_angle():
    assert abs(joint_angle(np.array([1, 0]), np.array([0, 0]), np.array([0, 1])) - 90) < 1e-3


def test_collinear():
    assert abs(joint_angle(np.array([-1, 0]), np.array([0, 0]), np.array([1, 0])) - 180) < 1e-2


def test_trunk_vertical_and_tilted():
    kp = np.zeros((17, 2))
    kp[5] = kp[6] = [0, 0]
    kp[11] = kp[12] = [0, 10]
    assert trunk_angle(kp) < 1e-3
    kp[5] = kp[6] = [10, 0]
    assert abs(trunk_angle(kp) - 45) < 1e-3


def test_angle_series_interpolates_nan():
    people = []
    for i in range(9):
        kp = np.zeros((17, 2))
        kp[0], kp[1], kp[2] = [1, 0], [0, 0], [0, 1]
        conf = np.ones(17)
        if i == 4:
            conf[1] = 0.1
        people.append(Person(None, (0, 0, 1, 1), kp, conf))
    s = angle_series(people, {"j": [0, 1, 2]}, 0.5)["j"]
    assert not np.isnan(s).any()
    assert np.allclose(s, 90, atol=1e-3)


def test_point_in_zone():
    poly = [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]]
    assert point_in_zone((10, 10), poly, 100, 100)
    assert not point_in_zone((80, 80), poly, 100, 100)
