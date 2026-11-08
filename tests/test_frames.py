import cv2
import numpy as np
import pytest

from medwatch.video.frames import iter_frames, video_info
from medwatch.video.models import Person, main_person


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "v.mp4"
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 48))
    for i in range(60):
        w.write(np.full((48, 64, 3), i * 4, dtype=np.uint8))
    w.release()
    return path


def test_iter_frames_downsamples(video):
    frames = list(iter_frames(video, target_fps=10))
    assert 18 <= len(frames) <= 22
    ts = [f.t for f in frames]
    assert ts == sorted(ts) and ts[0] == 0
    assert frames[0].image.shape == (48, 64, 3)


def test_video_info(video):
    info = video_info(video)
    assert info["width"] == 64 and info["height"] == 48
    assert info["duration_s"] == pytest.approx(2.0, abs=0.2)


def test_missing_video(tmp_path):
    with pytest.raises(RuntimeError):
        list(iter_frames(tmp_path / "x.mp4", 10))


def test_main_person():
    kp = np.zeros((17, 2))
    small = Person(1, (0, 0, 10, 10), kp, np.ones(17))
    big = Person(2, (0, 0, 50, 50), kp, np.ones(17))
    assert main_person([small, big]) is big
    assert main_person([]) is None
