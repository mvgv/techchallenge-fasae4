from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from medwatch.audio.events import RespiratoryEventDetector

CFG = {
    "window_s": 1, "hop_s": 1, "min_score": 0.3,
    "labels": ["Cough", "Breathing", "Wheeze"],
}


def _wav(tmp_path: Path, seconds: float) -> Path:
    p = tmp_path / "a.wav"
    sf.write(p, np.zeros(int(16000 * seconds), dtype="float32"), 16000)
    return p


def test_aggregates_windows(tmp_path):
    calls = []

    def fake(_inp):
        calls.append(1)
        n = len(calls)
        return [
            {"label": "Cough", "score": 0.9 if n == 2 else 0.1},
            {"label": "Speech", "score": 0.99},
            {"label": "Breathing", "score": 0.5},
        ]

    det = RespiratoryEventDetector(CFG, clf=fake)
    res = det.detect(_wav(tmp_path, 3))
    assert len(calls) == 3
    assert [e["label"] for e in res] == ["Cough"]  # Breathing 0.5 ignorado
    assert res[0]["max_score"] == 0.9
    assert res[0]["windows"] == [{"t_start": 1.0, "score": 0.9}]


def test_breathing_high_score_and_short_audio(tmp_path):
    det = RespiratoryEventDetector(
        CFG, clf=lambda _i: [{"label": "Breathing", "score": 0.7}]
    )
    res = det.detect(_wav(tmp_path, 0.5))
    assert res[0]["label"] == "Breathing"
    assert len(res[0]["windows"]) == 1


@pytest.mark.slow
def test_real_model():
    sample = Path("data/samples/cough.wav")
    if not sample.exists():
        pytest.skip("sem data/samples/cough.wav")
    cfg = dict(CFG, window_s=10, hop_s=5)
    assert isinstance(RespiratoryEventDetector(cfg).detect(sample), list)
