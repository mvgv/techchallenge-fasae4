"""Testes da linha de base de voz com o Common Voice (dados mínimos criados no próprio teste)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_voice_baseline import baseline_from_rows  # noqa: E402
from evaluate_voice import (  # noqa: E402
    ID_LEN,
    evaluate,
    load_clips,
    make_sample,
    select_speakers,
    summarize,
    to_markdown,
    wilson,
)

CFG = {"speech_rate_wpm_min": 100, "pause_ratio_max": 0.40, "z_threshold": 2.0}


def _df(counts: dict[str, int]) -> pd.DataFrame:
    rows = []
    for spk, n in counts.items():
        for i in range(n):
            rows.append({"client_id": spk * 40, "path": f"{spk}_{i:02d}.mp3", "sentence": f"frase {i}"})
    df = pd.DataFrame(rows)
    df["spk"] = df["client_id"].str[:ID_LEN]
    return df


def test_select_speakers_applies_minimum_and_cap():
    out = select_speakers(_df({"a": 12, "b": 3, "c": 10}), min_clips=10, clips=10)
    assert sorted(out) == ["a" * ID_LEN, "c" * ID_LEN]
    assert len(out["a" * ID_LEN]) == 10  # limite por falante: um falante com centenas não domina
    assert [p for p, _ in out["a" * ID_LEN]] == sorted(p for p, _ in out["a" * ID_LEN])


def test_load_clips_joins_tsvs(tmp_path):
    for name, n in (("train.tsv", 2), ("dev.tsv", 1)):
        pd.DataFrame({"client_id": ["x" * 64] * n, "path": ["p"] * n, "sentence": ["s"] * n}).to_csv(
            tmp_path / name, sep="\t", index=False)
    df = load_clips(tmp_path)
    assert len(df) == 3 and (df["spk"] == "x" * ID_LEN).all()


def test_make_sample_trims_edges_and_builds_segments(tmp_path):
    (tmp_path / "clips").mkdir()
    t = np.arange(int(0.5 * 16000)) / 16000
    tone = (0.5 * np.sin(2 * np.pi * 200 * t)).astype("float32")
    silencio = np.zeros(16000, "float32")  # 1 s de silêncio de cada lado
    clip = np.concatenate([silencio, tone, silencio])
    for name in ("a.mp3", "b.mp3"):  # WAV com extensão .mp3: o soundfile identifica pelo conteúdo
        sf.write(tmp_path / "clips" / name, clip, 16000, format="WAV")
    segs = make_sample(tmp_path, [("a.mp3", "um dois"), ("b.mp3", "três")], tmp_path / "out.wav")
    assert len(segs) == 2
    assert all(0.4 < s.duration_s < 0.65 for s in segs)  # silêncio das pontas removido
    assert abs(segs[1].offset_s - segs[0].duration_s) < 1e-6
    info = sf.info(tmp_path / "out.wav")
    assert (info.samplerate, info.channels) == (16000, 1)
    assert 0.8 < info.duration < 1.3


def test_baseline_and_evaluate_flag_outlier_only():
    base_rows = [{"jitter": 0.02 + 0.001 * i, "shimmer_db": 0.5, "hnr": 12.0, "f0_var": 0.2,
                  "f0_mean": 30.0, "loudness": 0.5, "pause_ratio": 0.2} for i in range(10)]
    baseline = baseline_from_rows(base_rows)
    assert baseline["hnr"] == {"mean": 12.0, "std": 0.0}
    normal = dict(base_rows[3], speech_rate_wpm=150.0)
    atipico = dict(base_rows[0], speech_rate_wpm=60.0, pause_ratio=0.6)  # lento e com muitas pausas
    res = evaluate([normal, atipico], baseline, CFG)
    assert res["n"] == 2 and res["algum_alarme"] == 1
    assert res["por_tipo"]["voice_fatigue"] == 1
    assert res["sinais"]["slow_speech"] == 1 and res["sinais"]["many_pauses"] == 1


def test_wilson_interval():
    lo, hi = wilson(2, 27)
    assert 0.015 < lo < 0.03 and 0.2 < hi < 0.26
    assert wilson(0, 10)[0] == 0.0 and wilson(10, 10)[1] == 1.0
    assert wilson(0, 0) == (0.0, 1.0)


def test_markdown_summary_mentions_rates_and_limitations():
    dist = {k: {"media": 1.0, "p5": 0.5, "p95": 2.0} for k in
            ("speech_rate_wpm", "pause_ratio", "jitter", "shimmer_db", "hnr", "loudness", "duration_s")}
    ev = {"n": 27, "algum_alarme": 2, "taxa": 0.074, "sinais": {"slow_speech": 2},
          "por_tipo": {"voice_fatigue": 2, "voice_dysarthria_indicator": 0}}
    md = to_markdown({"limiares": CFG, "calibracao": dict(ev, n=54, algum_alarme=1, taxa=0.019),
                      "reservado": ev, "distribuicao": {"calibracao": dist, "reservado": dist}})
    assert "7.4%" in md and "IC 95%" in md and "Limitações" in md and "slow_speech" in md


def test_summarize_percentiles():
    s = summarize([{"x": v} for v in range(1, 101)], "x")
    assert s["media"] == 50.5 and s["p5"] <= 6 and s["p95"] >= 95
    assert summarize([{"x": None}], "x") == {}
