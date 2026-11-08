import importlib.util
from pathlib import Path

from medwatch.audio.speech import FakeTranscriber, get_transcriber
from medwatch.config import get_settings


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "check_azure.py"
    spec = importlib.util.spec_from_file_location("check_azure", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_check_azure_fake_mode(monkeypatch, capsys):
    monkeypatch.setenv("USE_FAKE_AZURE", "true")
    get_settings.cache_clear()
    try:
        assert _load_script().main() == 0
        assert "modo fake" in capsys.readouterr().out
        assert isinstance(get_transcriber(), FakeTranscriber)
    finally:
        get_settings.cache_clear()


def test_get_transcriber_without_key_raises(monkeypatch):
    monkeypatch.setenv("USE_FAKE_AZURE", "false")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "")
    get_settings.cache_clear()
    try:
        try:
            get_transcriber()
        except RuntimeError as exc:
            assert "AZURE_SPEECH_KEY" in str(exc)
        else:
            raise AssertionError("deveria falhar sem chave")
    finally:
        get_settings.cache_clear()
