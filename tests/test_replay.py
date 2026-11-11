import json
from datetime import UTC, datetime

import fakeredis

from medwatch.bus import Bus
from medwatch.config import get_settings
from medwatch.simulator import replay

START = datetime(2026, 1, 1, 19, 0, tzinfo=UTC)


def test_speedup_phases():
    assert replay.speedup_at(replay.DEMO_PHASES, 10) == 60
    assert replay.speedup_at(replay.DEMO_PHASES, 360) == 6


def test_default_start_demo():
    s = replay.default_start("demo", datetime(2026, 1, 2, 12, 30, tzinfo=UTC))
    assert s == datetime(2026, 1, 1, 19, 0, tzinfo=UTC)


def test_fast_run_publishes_and_writes_truth(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "local_storage_dir", tmp_path)
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    n = replay.run("hypotension", 2, 60, START, fast=True, bus=bus)
    assert n == bus.r.xlen("vitals") + bus.r.xlen("prescriptions") + bus.r.xlen("movement")
    assert bus.r.xlen("vitals") == 2 * 24 * 60
    assert bus.r.get("sim:clock")
    labels = json.loads((tmp_path / "ground_truth" / "hypotension.json").read_text())
    assert len(labels) == 2


def test_sleeps_scaled_by_phase(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "local_storage_dir", tmp_path)
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    sleeps: list[float] = []
    replay.run("demo", 5, 60, START, bus=bus, sleep=sleeps.append)
    assert sleeps[0] == 1.0          # 60 s simulados a 60x
    assert sleeps[-1] == 10.0        # 60 s simulados a 6x
    assert len(sleeps) == 479
    assert bus.r.xlen("vitals") == 5 * 480


def test_demo_phases_tail_speedup():
    assert replay.demo_phases() == replay.DEMO_PHASES
    phases = replay.demo_phases(12)
    assert replay.speedup_at(phases, 10) == 60
    assert replay.speedup_at(phases, 400) == 12


def test_fast_until_skips_sleep_then_follows_phases(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "local_storage_dir", tmp_path)
    bus = Bus(fakeredis.FakeRedis(decode_responses=True))
    sleeps: list[float] = []
    replay.run("demo", 5, 60, START, bus=bus, sleep=sleeps.append,
               fast_until=355, tail_speedup=12)
    assert sleeps[0] == 1.0 and sleeps[-1] == 5.0   # 355–360 ainda a 60x; depois 60 s a 12x
    assert len(sleeps) < 140                         # a hora inicial (360 min) foi sem espera
    assert 9 * 60 < sum(sleeps) < 11 * 60            # trecho 360–480 em ~10 min reais
