"""Barramento de mensagens sobre Redis Streams."""
import json
import logging
import socket
import time
from collections.abc import Callable

import redis
from pydantic import BaseModel

from medwatch.config import get_settings

log = logging.getLogger(__name__)


class Bus:
    def __init__(self, client: redis.Redis | None = None):
        self.r = client or redis.Redis.from_url(get_settings().redis_url, decode_responses=True)

    def publish(self, stream: str, msg: BaseModel | dict) -> str:
        """Publica uma mensagem no stream."""
        data = msg.model_dump_json() if isinstance(msg, BaseModel) else json.dumps(msg, default=str)
        return self.r.xadd(stream, {"data": data}, maxlen=200_000, approximate=True)

    def ensure_group(self, stream: str, group: str) -> None:
        """Cria o consumer group se não existir."""
        try:
            self.r.xgroup_create(stream, group, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    def consume(self, streams: list[str], group: str, handler: Callable[[str, dict], None],
                block_ms: int = 5000, count: int = 20, stop_after: int | None = None) -> None:
        """Loop de consumo. handler(stream, payload). Mensagens com erro não recebem ACK."""
        consumer = f"{group}-{socket.gethostname()}"
        for s in streams:
            self.ensure_group(s, group)
        processed = 0
        while True:
            resp = self.r.xreadgroup(group, consumer, {s: ">" for s in streams},
                                     count=count, block=block_ms)
            for stream, messages in resp or []:
                for msg_id, fields in messages:
                    try:
                        handler(stream, json.loads(fields["data"]))
                        self.r.xack(stream, group, msg_id)
                    except Exception:
                        log.exception("Falha ao processar %s %s", stream, msg_id)
                    processed += 1
            if stop_after is not None and processed >= stop_after:
                return
            if not resp:
                time.sleep(0.05)
