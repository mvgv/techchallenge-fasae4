import json
from datetime import UTC, datetime
from uuid import uuid4

import fakeredis
import numpy as np
import pytest
import soundfile as sf

from medwatch.audio.worker import AudioWorker
from medwatch.bus import Bus
from medwatch.config import get_settings
from medwatch.contracts import MediaJob
from medwatch.storage import LocalStorage


class FakeDb:
    def __init__(self):
        self.media, self.transcripts = [], []

    def update_media(self, media_id, **kw):
        self.media.append(kw)

    def insert_transcript(self, media_id, language, segments, analysis):
        self.transcripts.append((segments, analysis))


class FakeDetector:
    def detect(self, wav):
        return [{"label": "Cough", "max_score": 0.8, "windows": [{"t_start": 2.0, "score": 0.8}]}]


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_FAKE_AZURE", "true")
    get_settings.cache_clear()
    wav = tmp_path / "in.wav"
    noise = np.random.default_rng(0).normal(0, 0.05, 16000 * 16).astype("float32")
    sf.write(wav, noise, 16000)
    st = LocalStorage(tmp_path / "store")
    uri = st.put_file(wav, "media/in.wav")
    job = MediaJob(media_id=uuid4(), patient_id="P-0001", kind="audio", storage_uri=uri,
                   recorded_at=datetime(2026, 1, 1, 8, tzinfo=UTC), patient_speaker="Guest-2")
    return job, st, Bus(fakeredis.FakeRedis(decode_responses=True))


def test_audio_worker_publishes_terms(tmp_path, monkeypatch):
    job, st, bus = _setup(tmp_path, monkeypatch)
    db = FakeDb()
    evs = AudioWorker(bus, st, db, detector=FakeDetector(), baseline={}).process(job)
    assert {"speech_critical_term", "respiratory_sound"} <= {e.type for e in evs}
    assert any(e.payload.get("term") == "falta de ar" for e in evs)
    assert db.media[0]["status"] == "processing" and db.media[-1]["status"] == "done"
    assert db.transcripts and bus.r.xlen("evidence") == len(evs)
    art = tmp_path / "store" / db.media[-1]["artifacts"]["analysis"]
    assert "terms" in json.loads(art.read_text())


def test_audio_worker_failure_marks_failed(tmp_path, monkeypatch):
    job, st, bus = _setup(tmp_path, monkeypatch)
    job.storage_uri = "local://nao/existe.wav"
    db = FakeDb()
    w = AudioWorker(bus, st, db, detector=FakeDetector(), baseline={})
    with pytest.raises(Exception):  # noqa: B017 - qualquer falha deve ser relançada
        w.process(job)
    assert db.media[-1]["status"] == "failed"
