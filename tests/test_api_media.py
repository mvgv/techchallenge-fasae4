import json
from uuid import uuid4

import fakeredis
import pytest
from fastapi.testclient import TestClient

from medwatch import db
from medwatch.api.deps import get_bus, get_storage_dep
from medwatch.api.main import app
from medwatch.bus import Bus
from medwatch.storage import LocalStorage

pytestmark = pytest.mark.skipif(not db.ping(), reason="banco indisponível")


@pytest.fixture()
def env(tmp_path):
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    storage = LocalStorage(tmp_path)
    app.dependency_overrides[get_bus] = lambda: bus
    app.dependency_overrides[get_storage_dep] = lambda: storage
    pid = f"T-{uuid4().hex[:8]}"
    db.upsert_patient(pid, "Teste", "L1")
    yield TestClient(app), bus, pid
    app.dependency_overrides.clear()


def test_audio_upload_publishes_job(env):
    client, bus, pid = env
    r = client.post("/media", data={"patient_id": pid, "kind": "audio"},
                    files={"file": ("a.wav", b"RIFFxxxx", "audio/wav")})
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    msgs = bus.r.xrange("jobs.audio")
    assert len(msgs) == 1
    assert json.loads(msgs[0][1]["data"])["media_id"] == body["media_id"]
    assert client.get(f"/media/{body['media_id']}").json()["status"] == "queued"


def test_invalid_extension_422(env):
    client, _, pid = env
    r = client.post("/media", data={"patient_id": pid, "kind": "audio"},
                    files={"file": ("a.exe", b"x")})
    assert r.status_code == 422


def test_unknown_patient_404(env):
    client, _, _ = env
    r = client.post("/media", data={"patient_id": "NAO-EXISTE", "kind": "audio"},
                    files={"file": ("a.wav", b"x")})
    assert r.status_code == 404


def test_physio_without_exercise_422(env):
    client, _, pid = env
    r = client.post("/media", data={"patient_id": pid, "kind": "video", "mode": "physio"},
                    files={"file": ("v.mp4", b"x")})
    assert r.status_code == 422


def test_document_and_files(env):
    client, bus, pid = env
    r = client.post("/documents", json={"patient_id": pid, "text": "dor no peito"})
    assert r.status_code == 202
    assert len(bus.r.xrange("jobs.text")) == 1
    key = db.get_media(r.json()["media_id"])["storage_uri"].removeprefix("local://")
    assert client.get(f"/files/{key}").content == b"dor no peito"
    assert client.get("/files/x/../../etc/passwd").status_code in (400, 404)
    assert client.get("/files/%2e%2e/secret").status_code in (400, 404)
