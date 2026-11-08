import random
from datetime import UTC, datetime, timedelta

from medwatch.anomaly.streaming_stats import Cooldown, EwmaZ


def _noisy(n: int, rng: random.Random, base: float = 80.0, sd: float = 1.0) -> list[float]:
    return [base + rng.gauss(0, sd) for _ in range(n)]


def test_warmup_returns_zero():
    rng = random.Random(1)
    ewma = EwmaZ(alpha=0.1, warmup=20)
    zs = [ewma.update(x) for x in _noisy(20, rng)]
    assert all(z == 0.0 for z in zs)


def test_step_is_detected():
    rng = random.Random(2)
    ewma = EwmaZ(alpha=0.1, warmup=20)
    for x in _noisy(60, rng):
        ewma.update(x)
    std = ewma.var**0.5
    z = ewma.update(ewma.mean + 10 * std)
    assert abs(z) > 3


def test_cooldown():
    cd = Cooldown()
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    key = ("p0001", "hr")
    assert cd.ready(key, t0, 5)
    assert not cd.ready(key, t0 + timedelta(minutes=2), 5)
    assert cd.ready(key, t0 + timedelta(minutes=5), 5)
    assert cd.ready(("p0002", "hr"), t0, 5)
