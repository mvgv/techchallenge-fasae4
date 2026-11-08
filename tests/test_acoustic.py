import numpy as np
import pytest
import soundfile as sf

from medwatch.audio.acoustic import assess_voice, extract_features
from medwatch.audio.speech import Segment

CFG = dict(speech_rate_wpm_min=100, pause_ratio_max=0.40, z_threshold=2.0)


@pytest.fixture
def wav(tmp_path):
    t = np.arange(16000) / 16000
    tone = 0.5 * np.sin(2 * np.pi * 150 * t)
    y = np.concatenate([tone, np.zeros(16000), tone, np.zeros(16000)]).astype("float32")
    p = tmp_path / "v.wav"
    sf.write(str(p), y, 16000)
    return p


def test_pause_ratio_and_rate(wav):
    segs = [Segment("A", "um dois tres quatro", 0.0, 4.0)]
    f = extract_features(wav, segs, None)
    assert 0 < f["pause_ratio"] < 1
    assert f["pause_ratio"] == pytest.approx(0.5, abs=0.1)
    assert f["speech_rate_wpm"] == pytest.approx(60.0)
    assert f["duration_s"] == pytest.approx(4.0, abs=0.1)


def test_patient_speaker_filter(wav):
    segs = [Segment("A", "um dois", 0.0, 2.0), Segment("B", "tres", 2.0, 2.0)]
    f = extract_features(wav, segs, "A")
    assert f["duration_s"] == pytest.approx(2.0, abs=0.1)


def test_fatigue_without_baseline():
    r = assess_voice(dict(speech_rate_wpm=70, pause_ratio=0.5), None, CFG)
    assert len(r) == 1
    typ, score, flags = r[0]
    assert typ == "voice_fatigue"
    assert score == pytest.approx(2 / 3)
    assert flags["baseline_missing"] is True


def test_no_alert_normal():
    assert assess_voice(dict(speech_rate_wpm=130, pause_ratio=0.2), None, CFG) == []


def test_dysarthria_needs_baseline():
    base = {k: dict(mean=1.0, std=0.1) for k in
            ("f0_mean", "f0_var", "jitter", "shimmer_db", "hnr", "loudness")}
    feats = dict(speech_rate_wpm=130, pause_ratio=0.2, jitter=2.0,
                 shimmer_db=2.0, hnr=1.0, f0_var=1.0)
    assert assess_voice(feats, None, CFG) == []
    r = assess_voice(feats, base, CFG)
    assert r[0][0] == "voice_dysarthria_indicator"
    assert r[0][1] == pytest.approx(0.5)
