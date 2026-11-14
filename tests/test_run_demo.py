"""Testes do roteiro automatizado da demo (scripts/run_demo.py)."""
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import fakeredis
import httpx

_spec = importlib.util.spec_from_file_location(
    "run_demo", Path(__file__).resolve().parents[1] / "scripts" / "run_demo.py")
rd = importlib.util.module_from_spec(_spec)
sys.modules["run_demo"] = rd
_spec.loader.exec_module(rd)

START = datetime(2026, 11, 7, 19, 0, tzinfo=UTC)


class Recorder:
    """Handler do MockTransport que guarda as requisições."""

    def __init__(self, status: int = 202):
        self.requests: list[httpx.Request] = []
        self.status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path == "/patients":
            return httpx.Response(201, json=json.loads(request.content))
        return httpx.Response(self.status, json={"media_id": f"m{len(self.requests)}"})


def _client(rec: Recorder) -> httpx.Client:
    return httpx.Client(base_url="http://api", transport=httpx.MockTransport(rec))


def _samples(tmp_path: Path, skip: set[str] = frozenset()) -> Path:
    for step in rd.DEMO_STEPS:
        if step.filename in skip:
            continue
        p = tmp_path / step.filename
        if step.kind == "document":
            p.write_text("Paciente em uso de heparina. Sangramento discreto.", encoding="utf-8")
        else:
            p.write_bytes(b"\x00" * 16)
    return tmp_path


class Clock:
    """Sleep falso: cada chamada avança `sim:clock` em `step` minutos."""

    def __init__(self, r, minutes: list[float]):
        self.r = r
        self.minutes = list(minutes)
        self.calls = 0

    def __call__(self, _seconds: float) -> None:
        self.calls += 1
        if self.minutes:
            m = self.minutes.pop(0)
            self.r.set("sim:clock", (START + timedelta(minutes=m)).isoformat())


def _media_form(req: httpx.Request) -> str:
    return req.content.decode("latin-1")


def test_run_demo_sends_each_sample_at_its_minute(tmp_path):
    r = fakeredis.FakeRedis(decode_responses=True)
    rec = Recorder()
    clock = Clock(r, [0, 200, 364, 366, 371, 380, 386, 409, 411, 479])
    result = rd.run_demo(_client(rec), r, START, _samples(tmp_path), sleep=clock)

    assert result["sent"] == [s.filename for s in rd.DEMO_STEPS]
    assert result["skipped"] == [] and result["failed"] == []
    paths = [q.url.path for q in rec.requests]
    assert paths == ["/media", "/media", "/documents", "/media"]
    # recorded_at = sim:clock do momento do envio
    physio = _media_form(rec.requests[0])
    assert "physio_squat_wrong.mp4" in physio and "P-0003" in physio
    assert (START + timedelta(minutes=366)).isoformat() in physio
    assert 'name="mode"' in physio and "squat" in physio
    audio = _media_form(rec.requests[1])
    assert "consulta_p0001.wav" in audio and (START + timedelta(minutes=371)).isoformat() in audio
    doc = json.loads(rec.requests[2].content)
    assert doc["patient_id"] == "P-0002" and "heparina" in doc["text"]
    assert doc["recorded_at"] == (START + timedelta(minutes=386)).isoformat()
    fall = _media_form(rec.requests[3])
    assert "bed_fall.mp4" in fall and "P-0004" in fall and "bed" in fall
    # a queda do UR Fall acontece dentro do polígono de default_bed: sem camera=ur_fall a regra a ignora
    assert 'name="camera"' in fall and "ur_fall" in fall


def test_run_demo_waits_for_clock_and_skips_missing(tmp_path):
    r = fakeredis.FakeRedis(decode_responses=True)
    rec = Recorder()
    # duas leituras sem relógio antes do simulador publicar
    seq = iter([None, None, 370, 479])

    def sleep(_s):
        m = next(seq, None)
        if m is not None:
            r.set("sim:clock", (START + timedelta(minutes=m)).isoformat())

    samples = _samples(tmp_path, skip={"bed_fall.mp4", "consulta_p0001.wav"})
    result = rd.run_demo(_client(rec), r, START, samples, sleep=sleep)
    assert result["sent"] == ["physio_squat_wrong.mp4", "laudo_p0002.txt"]
    assert result["skipped"] == ["consulta_p0001.wav", "bed_fall.mp4"]
    assert rd.missing_samples(samples) == ["consulta_p0001.wav", "bed_fall.mp4"]


def test_run_demo_stops_when_simulator_exits(tmp_path):
    r = fakeredis.FakeRedis(decode_responses=True)
    r.set("sim:clock", (START + timedelta(minutes=366)).isoformat())

    class DeadProc:
        def poll(self):
            return 0

    rec = Recorder(status=500)
    result = rd.run_demo(_client(rec), r, START, _samples(tmp_path), proc=DeadProc(),
                         sleep=lambda s: None)
    assert result["failed"] == ["physio_squat_wrong.mp4"]
    assert result["skipped"] == ["consulta_p0001.wav", "laudo_p0002.txt", "bed_fall.mp4"]


def test_health_and_seed():
    rec = Recorder()
    client = _client(rec)
    assert rd.check_health(client)
    rd.seed_patients(client)
    bodies = [json.loads(q.content) for q in rec.requests if q.url.path == "/patients"]
    assert [b["patient_id"] for b in bodies] == [f"P-{i:04d}" for i in range(1, 6)]
    assert bodies[0] == {"patient_id": "P-0001", "display_name": "Paciente 01", "bed": "UTI-01"}

    def down(_req):
        raise httpx.ConnectError("refused")

    assert not rd.check_health(httpx.Client(base_url="http://api",
                                            transport=httpx.MockTransport(down)))


def test_steps_match_table_7_1():
    by_patient = {s.patient_id: (s.minute, s.filename) for s in rd.DEMO_STEPS}
    assert by_patient == {
        "P-0003": (365, "physio_squat_wrong.mp4"), "P-0001": (370, "consulta_p0001.wav"),
        "P-0002": (385, "laudo_p0002.txt"), "P-0004": (410, "bed_fall.mp4")}
