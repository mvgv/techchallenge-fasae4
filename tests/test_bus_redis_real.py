"""Teste contra um Redis de verdade (pula se não houver), para o comportamento de bloqueio.

O fakeredis não bloqueia, então não reproduz o TimeoutError do redis-py 8 em leituras
bloqueantes vazias (corrigido em medwatch.bus.SOCKET_TIMEOUT_S).
"""
import uuid

import pytest
import redis

from medwatch.bus import SOCKET_TIMEOUT_S, Bus
from medwatch.config import get_settings


def _real_bus() -> Bus:
    bus = Bus()
    try:
        bus.r.ping()
    except redis.exceptions.RedisError:
        pytest.skip(f"sem Redis em {get_settings().redis_url}")
    return bus


def test_blocking_read_on_empty_stream_returns_empty():
    bus = _real_bus()
    stream = f"teste.vazio.{uuid.uuid4().hex}"
    try:
        bus.ensure_group(stream, "g")
        resp = bus.r.xreadgroup("g", "c", {stream: ">"}, count=1, block=1000)
        assert resp == []
    finally:
        bus.r.delete(stream)


def test_publish_and_consume_with_real_redis():
    bus = _real_bus()
    stream = f"teste.fluxo.{uuid.uuid4().hex}"
    seen: list[dict] = []
    try:
        bus.publish(stream, {"n": 1})
        bus.consume([stream], "g", lambda _s, p: seen.append(p), block_ms=500, stop_after=1)
        assert seen == [{"n": 1}]
        assert bus.r.xpending(stream, "g")["pending"] == 0
    finally:
        bus.r.delete(stream)


def test_block_ms_above_socket_timeout_is_rejected():
    bus = Bus()
    with pytest.raises(ValueError):
        bus.consume(["x"], "g", lambda _s, _p: None, block_ms=SOCKET_TIMEOUT_S * 1000)
