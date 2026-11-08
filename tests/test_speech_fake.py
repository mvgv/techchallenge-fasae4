import shutil

import numpy as np
import pytest
import soundfile as sf

from medwatch.audio.convert import duration_seconds, to_wav_16k_mono
from medwatch.audio.speech import AzureTranscriber, FakeTranscriber, get_transcriber
from medwatch.config import get_settings


def _tone(path, sr=44100, secs=1.0):
    t = np.linspace(0, secs, int(sr * secs), endpoint=False)
    sf.write(str(path), 0.3 * np.sin(2 * np.pi * 440 * t), sr)


def test_fake_transcriber_segments(tmp_path):
    segs = FakeTranscriber().transcribe(tmp_path / "x.wav")
    assert len(segs) == 4
    assert segs[1].speaker == "Guest-2" and "falta de ar" in segs[1].text
    assert [s.offset_s for s in segs] == sorted(s.offset_s for s in segs)


def test_factory_fake(monkeypatch):
    monkeypatch.setenv("USE_FAKE_AZURE", "true")
    get_settings.cache_clear()
    try:
        assert isinstance(get_transcriber(), FakeTranscriber)
    finally:
        get_settings.cache_clear()


def test_factory_requires_key(monkeypatch):
    monkeypatch.setenv("USE_FAKE_AZURE", "false")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="AZURE_SPEECH_KEY"):
            get_transcriber()
    finally:
        get_settings.cache_clear()


def test_azure_transcriber_attrs():
    t = AzureTranscriber("k", "brazilsouth", "pt-BR")
    assert (t.key, t.region, t.language) == ("k", "brazilsouth", "pt-BR")


def test_duration_seconds(tmp_path):
    p = tmp_path / "a.wav"
    _tone(p, sr=16000, secs=2.0)
    assert duration_seconds(p) == pytest.approx(2.0, abs=0.01)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")
def test_convert_to_16k_mono(tmp_path):
    src, dst = tmp_path / "in.wav", tmp_path / "out" / "o.wav"
    _tone(src)
    assert to_wav_16k_mono(src, dst) == dst
    info = sf.info(str(dst))
    assert (info.samplerate, info.channels, info.subtype) == (16000, 1, "PCM_16")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg ausente")
def test_convert_error(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"nao e audio")
    with pytest.raises(RuntimeError, match="ffmpeg"):
        to_wav_16k_mono(bad, tmp_path / "o.wav")
