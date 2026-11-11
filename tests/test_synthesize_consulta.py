"""Testes do gerador de consulta sintética, com sintetizador falso (nenhuma chamada à Azure)."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from synthesize_consulta import (  # noqa: E402
    CONSULTA,
    DOCTOR_VOICE,
    PATIENT_VOICE,
    SR,
    Fala,
    assemble,
    build_ssml,
    load_coughs,
    write_wav,
)


def fake_synth(voice: str, text: str, rate: int = 0) -> np.ndarray:
    """0,1 s de seno por palavra; frequência diferente para cada voz."""
    freq = 220 if voice == DOCTOR_VOICE else 140
    n = int(0.1 * SR * len(text.split()))
    return (0.3 * np.sin(2 * np.pi * freq * np.arange(n) / SR)).astype("float32")


def test_ssml_escapes_text_and_slow_rate_adds_pauses():
    s = build_ssml(PATIENT_VOICE, "Dor & febre, tosse", -20)
    assert "Dor &amp; febre" in s
    assert "<break" in s
    assert "rate='-20%'" in s
    assert "<break" not in build_ssml(DOCTOR_VOICE, "Bom dia, seu João", 0)


def test_script_matches_plan_and_has_two_voices_and_coughs():
    voices = {f.voice for f in CONSULTA}
    assert voices == {DOCTOR_VOICE, PATIENT_VOICE}
    assert sum(f.coughs_after for f in CONSULTA) == 2
    text = " ".join(f.text for f in CONSULTA)
    for termo in ("falta de ar", "cansaço", "febre", "dor no peito", "tusso"):
        assert termo in text


def test_assemble_inserts_coughs_and_pauses():
    cough = np.full(int(0.5 * SR), 0.5, dtype="float32")
    sem = assemble(CONSULTA, fake_synth, [])
    com = assemble(CONSULTA, fake_synth, [cough])
    extra = 2 * (0.5 + 0.35) * SR  # duas tosses, cada uma com 0,35 s de pausa antes
    assert abs((len(com) - len(sem)) - extra) < 2
    assert com.dtype == np.float32
    assert float(np.max(np.abs(com))) <= 1.0


def test_assemble_without_coughs_ignores_coughs_after():
    a = assemble([Fala(DOCTOR_VOICE, "um dois", coughs_after=3)], fake_synth, [])
    b = assemble([Fala(DOCTOR_VOICE, "um dois", coughs_after=0)], fake_synth, [])
    assert len(a) == len(b)


def test_write_wav_is_16k_mono_pcm16(tmp_path):
    out = tmp_path / "x" / "consulta.wav"
    write_wav(out, assemble(CONSULTA, fake_synth, []))
    info = sf.info(out)
    assert (info.samplerate, info.channels, info.subtype) == (16000, 1, "PCM_16")


def test_load_coughs_uses_only_reserved_folds(tmp_path):
    (tmp_path / "meta").mkdir()
    (tmp_path / "audio").mkdir()
    rows = [("1-a.wav", "1", "coughing"), ("4-b.wav", "4", "coughing"),
            ("5-c.wav", "5", "coughing"), ("4-d.wav", "4", "dog")]
    (tmp_path / "meta" / "esc50.csv").write_text(
        "filename,fold,target,category\n" + "\n".join(f"{f},{fo},0,{c}" for f, fo, c in rows),
        encoding="utf-8")
    t = np.arange(44100) / 44100
    for f, _, _ in rows:
        sf.write(tmp_path / "audio" / f, (0.5 * np.sin(2 * np.pi * 300 * t)).astype("float32"), 44100)
    clips = load_coughs(tmp_path, 5)
    assert len(clips) == 2  # só os folds 4 e 5 de tosse (a do fold 1 e o cachorro ficam de fora)
    assert all(abs(float(np.max(np.abs(c))) - 0.6) < 0.01 for c in clips)
