import fakeredis
from pydantic import BaseModel

from medwatch.bus import Bus


class Msg(BaseModel):
    n: int


def make_bus() -> Bus:
    return Bus(fakeredis.FakeRedis(decode_responses=True))


def test_publish_consume_three():
    bus = make_bus()
    bus.publish("s", Msg(n=1))
    bus.publish("s", {"n": 2})
    bus.publish("s", Msg(n=3))
    got = []
    bus.consume(["s"], "g", lambda s, p: got.append((s, p["n"])), block_ms=10, stop_after=3)
    assert got == [("s", 1), ("s", 2), ("s", 3)]
    assert bus.r.xpending("s", "g")["pending"] == 0


def test_failed_handler_not_acked():
    bus = make_bus()
    bus.publish("s", {"n": 1})

    def boom(s, p):
        raise RuntimeError("x")

    bus.consume(["s"], "g", boom, block_ms=10, stop_after=1)
    assert bus.r.xpending("s", "g")["pending"] == 1
