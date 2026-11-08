"""Dependências injetáveis (Bus e Storage) da API."""
from functools import lru_cache

from medwatch.bus import Bus
from medwatch.storage import Storage, get_storage


@lru_cache(maxsize=1)
def _bus() -> Bus:
    return Bus()


def get_bus() -> Bus:
    return _bus()


def get_storage_dep() -> Storage:
    return get_storage()
