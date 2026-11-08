from datetime import UTC, datetime
from uuid import uuid4

import fakeredis

from medwatch.bus import Bus
from medwatch.config import get_settings
from medwatch.contracts import MediaJob
from medwatch.storage import LocalStorage
from medwatch.text.worker import TextWorker, split_paragraphs


class FakeDb:
    def __init__(self):
        self.media = []

    def update_media(self, media_id, **kw):
        self.media.append(kw)


def test_split_paragraphs_limit():
    parts = split_paragraphs("a " * 4000 + "\n\nfim")
    assert all(len(p) <= 5000 for p in parts) and parts[-1] == "fim"


def test_text_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("USE_FAKE_AZURE", "true")
    get_settings.cache_clear()
    f = tmp_path / "n.txt"
    f.write_text("Paciente refere falta de ar.\n\nSem outras queixas.", encoding="utf-8")
    st = LocalStorage(tmp_path / "store")
    job = MediaJob(media_id=uuid4(), patient_id="P-0001", kind="document",
                   storage_uri=st.put_file(f, "media/n.txt"),
                   recorded_at=datetime(2026, 1, 1, tzinfo=UTC))
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    db = FakeDb()
    evs = TextWorker(bus, st, db).process(job)
    assert any(e.type == "text_critical_term" and e.payload["term"] == "falta de ar" for e in evs)
    assert all(e.modality == "text" for e in evs)
    assert db.media[-1]["status"] == "done" and bus.r.xlen("evidence") == len(evs)
