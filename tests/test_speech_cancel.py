"""Cancelamento da Azure Speech: o fim do arquivo não é erro (áudio sem fala, como uma tosse)."""
from types import SimpleNamespace

from medwatch.audio.speech import cancellation_error


class _Reason:
    def __init__(self, name: str) -> None:
        self.name = name


def _evt(reason: str, details: str = "") -> SimpleNamespace:
    det = SimpleNamespace(reason=_Reason(reason), error_details=details)
    return SimpleNamespace(cancellation_details=det, error_details=details, reason=_Reason(reason))


def test_end_of_stream_is_not_an_error():
    assert cancellation_error(_evt("EndOfStream")) is None


def test_error_reason_returns_message():
    assert "chave inválida" in cancellation_error(_evt("Error", "chave inválida"))


def test_error_without_details_still_reported():
    assert cancellation_error(_evt("Error")) is not None


def test_plain_string_reason():
    assert cancellation_error(SimpleNamespace(reason="CancellationReason.EndOfStream")) is None
    assert cancellation_error(SimpleNamespace(reason="CancellationReason.Error")) is not None
