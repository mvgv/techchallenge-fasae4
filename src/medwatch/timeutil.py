"""Utilitários de tempo (sempre UTC com timezone)."""
from datetime import UTC, datetime


def utcnow() -> datetime:
    """Retorna o instante atual em UTC com timezone."""
    return datetime.now(UTC)


def parse_ts(s: str) -> datetime:
    """Interpreta ISO 8601 com ou sem 'Z'; sem timezone assume UTC."""
    dt = datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso(dt: datetime) -> str:
    """Formata como ISO 8601 em UTC (naive é tratado como UTC)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()
