import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import fakeredis
import numpy as np
import pytest

from medwatch.bus import Bus
from medwatch.contracts import MediaJob
from medwatch.storage import LocalStorage
from medwatch.video.models import Detection, Person
from medwatch.video.worker import VideoWorker

W, H, FPS = 160, 120, 10


class FakeDb:
    def __init__(self):
        self.media = []

    def update_media(self, media_id, **kw):
        self.media.append(kw)


class FakeResult:
    def __init__(self, img):
        self.img = img

    def plot(self):
        out = self.img.copy()
        cv2.circle(out, (10, 10), 3, (0, 255, 0), -1)
        return out


def _standing(scale: float = 1.0) -> Person:
    kp = np.zeros((17, 2))
    kp[:, 0] = 80
    kp[:, 1] = np.linspace(20, 100, 17)
    kp[11] = kp[12] = (80, 60)
    return Person(1, (60.0, 15.0, 100.0, 105.0), kp, np.ones(17))


def _lying() -> Person:
    kp = np.zeros((17, 2))
    kp[:, 0] = np.linspace(20, 140, 17)
    kp[:, 1] = 110
    kp[11] = kp[12] = (80, 110)
    return Person(1, (15.0, 95.0, 145.0, 118.0), kp, np.ones(17))


class FixedPose:
    def __call__(self, img):
        return [_standing()], FakeResult(img)


class FallingPose:
    """Em pé até 1 s, depois deitada no chão (quadril desce ~40% da altura)."""

    def __init__(self):
        self.n = 0

    def __call__(self, img):
        p = _standing() if self.n < FPS else _lying()
        self.n += 1
        return [p], FakeResult(img)


class FakeDetector:
    def __call__(self, img):
        return [Detection("scissors", 0.9, (2.0, 2.0, 12.0, 12.0))], None


def _video(path: Path, seconds: float) -> Path:
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(int(seconds * FPS)):
        img = np.full((H, W, 3), (i * 5) % 255, np.uint8)
        vw.write(img)
    vw.release()
    return path


def _setup(tmp_path, mode, seconds=3.0, **kw):
    st = LocalStorage(tmp_path / "store")
    uri = st.put_file(_video(tmp_path / "in.mp4", seconds), "media/in.mp4")
    job = MediaJob(media_id=uuid4(), patient_id="P-0001", kind="video", storage_uri=uri,
                   recorded_at=datetime(2026, 1, 1, 8, tzinfo=UTC), mode=mode, **kw)
    return job, st, Bus(fakeredis.FakeRedis(decode_responses=True))


def _worker(bus, st, db, pose_cls=FixedPose, **kw):
    return VideoWorker(bus, st, db, pose_factory=pose_cls, detector=FakeDetector(),
                       target_fps=FPS, ref_dir=Path("/nao/existe"), **kw)


def test_physio_reaches_done_and_writes_findings(tmp_path):
    job, st, bus = _setup(tmp_path, "physio", exercise="squat")
    db = FakeDb()
    _worker(bus, st, db).process(job)
    assert db.media[0]["status"] == "processing" and db.media[-1]["status"] == "done"
    arts = db.media[-1]["artifacts"]
    doc = json.loads((tmp_path / "store" / arts["findings"]).read_text())
    assert doc["mode"] == "physio" and doc["n_frames"] == 30
    assert "series" in doc and "knee_left" in doc["series"]
    video = tmp_path / "store" / arts["annotated"]
    assert video.stat().st_size > 0
    cap = cv2.VideoCapture(str(video))
    assert cap.isOpened() and int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) >= 25
    cap.release()


def test_bed_fall_publishes_evidence_movement_and_keyframe(tmp_path):
    job, st, bus = _setup(tmp_path, "bed", seconds=5.0, camera="sem_zona")
    db = FakeDb()
    evs = _worker(bus, st, db, pose_cls=FallingPose, zones={"sem_zona": {}}).process(job)
    falls = [e for e in evs if e.type == "fall_detected"]
    assert falls and falls[0].severity == "critical"
    assert falls[0].modality == "video" and falls[0].model_name == "yolov8n-pose+rules"
    assert falls[0].source_ref.startswith(f"media:{job.media_id}#t=")
    frame_key = falls[0].payload["frame_key"]
    assert (tmp_path / "store" / frame_key).exists()
    assert "t_video_s" in falls[0].payload
    assert bus.r.xlen("evidence") == len(evs)
    assert bus.r.xlen("movement") == 1
    _, fields = bus.r.xrange("movement")[0]
    sample = json.loads(fields["data"])
    assert sample["source"] == "video" and sample["patient_id"] == "P-0001"


class VanishingPose:
    """Em pé até 1 s; depois a pose não acha ninguém (pessoa no chão)."""

    def __init__(self):
        self.n = 0

    def __call__(self, img):
        self.n += 1
        return ([_standing()] if self.n <= FPS else []), FakeResult(img)


class LyingDetector:
    def __init__(self):
        self.confs = []

    def __call__(self, img, conf=0.35):
        self.confs.append(conf)
        return [Detection("person", 0.3, (15.0, 95.0, 145.0, 118.0))], None


def test_bed_detector_fallback_when_pose_vanishes(tmp_path):
    thr = {"video": {"keypoint_min_conf": 0.5, "inactivity_motion_max": 0.01,
                     "fall": {"window_s": 1.0, "hip_drop_min": 0.15, "lying_aspect_min": 1.3,
                              "lying_min_s": 0.5, "hip_from_box": True}}}
    job, st, bus = _setup(tmp_path, "bed", seconds=5.0, camera="sem_zona")
    det = LyingDetector()
    w = VideoWorker(bus, st, FakeDb(), pose_factory=VanishingPose, detector=det,
                    target_fps=FPS, ref_dir=Path("/nao/existe"), zones={"sem_zona": {}},
                    thresholds=thr)
    assert not [e for e in w.process(job) if e.type == "fall_detected"]
    assert det.confs == []   # sem `detector_fallback_conf`, o detector não roda no leito
    thr["video"]["fall"]["detector_fallback_conf"] = 0.25
    (tmp_path / "b").mkdir()
    job2, st2, bus2 = _setup(tmp_path / "b", "bed", seconds=5.0, camera="sem_zona")
    w2 = VideoWorker(bus2, st2, FakeDb(), pose_factory=VanishingPose, detector=det,
                     target_fps=FPS, ref_dir=Path("/nao/existe"), zones={"sem_zona": {}},
                     thresholds=thr)
    assert [e for e in w2.process(job2) if e.type == "fall_detected"]
    assert det.confs and set(det.confs) == {0.25}


def test_surgery_uses_detector(tmp_path):
    job, st, bus = _setup(tmp_path, "surgery", seconds=6.0)
    db = FakeDb()
    thr = {"video": {"keypoint_min_conf": 0.5, "instrument_out_min_s": 5, "count_window_s": 10}}
    evs = _worker(bus, st, db, thresholds=thr).process(job)
    out = [e for e in evs if e.type == "surgery_instrument_out_of_zone"]
    assert out and out[0].model_name == "yolov8n+rules"
    assert out[0].payload["seconds"] >= 5
    assert db.media[-1]["status"] == "done"


def test_unknown_exercise_marks_failed(tmp_path):
    job, st, bus = _setup(tmp_path, "physio", exercise="nao_existe")
    db = FakeDb()
    with pytest.raises(ValueError):
        _worker(bus, st, db).process(job)
    assert db.media[-1]["status"] == "failed"


@pytest.mark.slow
def test_real_sample_video(tmp_path):
    samples = sorted(Path("data/samples").glob("*.mp4")) if Path("data/samples").exists() else []
    if not samples:
        pytest.skip("sem vídeo em data/samples/")
    pytest.importorskip("ultralytics")
    st = LocalStorage(tmp_path / "store")
    uri = st.put_file(samples[0], "media/sample.mp4")
    job = MediaJob(media_id=uuid4(), patient_id="P-0001", kind="video", storage_uri=uri,
                   recorded_at=datetime(2026, 1, 1, 8, tzinfo=UTC), mode="physio",
                   exercise="squat")
    db = FakeDb()
    VideoWorker(Bus(fakeredis.FakeRedis(decode_responses=True)), st, db).process(job)
    assert db.media[-1]["status"] == "done"
