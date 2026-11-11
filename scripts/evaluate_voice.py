"""Linha de base de voz e falsos alarmes com o Common Voice pt-BR (T37, passo 9).

Cada falante (client_id) com pelo menos `--min-clips` clipes vira uma amostra: os primeiros
`--clips` clipes (ordenados pelo nome), com o silêncio das pontas aparado, concatenados num
trecho contínuo. Os falantes são divididos 2/3 para a calibração (linha de base) e 1/3 reservado
(`config/splits.yaml`, seção `voice`). A linha de base sai só da calibração; o reservado mede
quantas vozes saudáveis disparam `voice_fatigue` ou `voice_dysarthria_indicator` por engano.

Uso: python scripts/evaluate_voice.py [--cv-dir data/datasets/commonvoice/extracted/pt-BR]
Saídas: data/references/voice_baseline.json (fora do Git) e docs/resultados/voice_baseline.{md,json}.
Os áudios nunca saem de data/ (os termos do Common Voice proíbem re-hospedar e identificar falantes).
"""
from __future__ import annotations

# ruff: noqa: E501  (texto do resumo em Markdown; reformatar as frases só atrapalharia a leitura)
import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_voice_baseline import baseline_from_rows  # noqa: E402
from make_splits import load_splits, save_section, split_ids  # noqa: E402

from medwatch.audio.acoustic import SR, extract_features  # noqa: E402
from medwatch.audio.acoustic import assess_voice as _assess  # noqa: E402
from medwatch.audio.speech import Segment  # noqa: E402
from medwatch.config import load_yaml  # noqa: E402

CV_DIR = ROOT / "data" / "datasets" / "commonvoice" / "extracted" / "pt-BR"
TSVS = ("train.tsv", "dev.tsv", "test.tsv")
ID_LEN = 16  # prefixo do client_id (já é um hash) gravado em config/splits.yaml


def load_clips(cv_dir: Path) -> pd.DataFrame:
    """Une os TSVs do recorte (train, dev e test) numa tabela; `spk` é o prefixo do client_id."""
    frames = [pd.read_csv(cv_dir / f, sep="\t", quoting=3, dtype=str) for f in TSVS
              if (cv_dir / f).exists()]
    if not frames:
        raise FileNotFoundError(f"nenhum TSV em {cv_dir}")
    df = pd.concat(frames, ignore_index=True)
    df["spk"] = df["client_id"].str[:ID_LEN]
    return df


def select_speakers(df: pd.DataFrame, min_clips: int, clips: int) -> dict[str, list[tuple[str, str]]]:
    """Falantes com `min_clips`+ clipes; de cada um, os `clips` primeiros (por nome): (path, frase)."""
    out: dict[str, list[tuple[str, str]]] = {}
    for spk, g in df.groupby("spk"):
        if len(g) >= min_clips:
            g = g.sort_values("path").head(clips)
            out[spk] = list(zip(g["path"], g["sentence"].fillna(""), strict=True))
    return out


def make_sample(cv_dir: Path, clips: list[tuple[str, str]], out_wav: Path) -> list[Segment]:
    """Concatena os clipes (sem as pontas silenciosas) em `out_wav` e devolve um Segment por clipe."""
    import librosa
    import soundfile as sf

    parts, segments, t = [], [], 0.0
    for path, sentence in clips:
        y, _ = librosa.load(str(cv_dir / "clips" / path), sr=SR, mono=True)
        y, _ = librosa.effects.trim(y, top_db=30)
        if len(y) == 0:
            continue
        dur = len(y) / SR
        segments.append(Segment("cv", sentence, t, dur))
        parts.append(y)
        t += dur
    sf.write(str(out_wav), np.concatenate(parts).astype("float32"), SR, subtype="PCM_16")
    return segments


def summarize(rows: list[dict], key: str) -> dict:
    vals = sorted(r[key] for r in rows if r.get(key) is not None)
    if not vals:
        return {}
    return {"media": round(statistics.fmean(vals), 3), "p5": round(vals[int(0.05 * (len(vals) - 1))], 3),
            "p95": round(vals[int(round(0.95 * (len(vals) - 1)))], 3)}


def evaluate(rows: list[dict], baseline: dict, cfg: dict) -> dict:
    """Quantos falantes saudáveis disparam cada evidência de voz."""
    flagged = {"voice_fatigue": 0, "voice_dysarthria_indicator": 0}
    any_flag = 0
    flags_count: dict[str, int] = {}
    for r in rows:
        res = _assess(r, baseline, cfg)
        any_flag += bool(res)
        for typ, _score, flags in res:
            flagged[typ] += 1
            for name, on in flags.items():
                if on is True and name != "baseline_missing":
                    flags_count[name] = flags_count.get(name, 0) + 1
    n = len(rows)
    return {"n": n, "algum_alarme": any_flag, "taxa": round(any_flag / n, 3) if n else None,
            "por_tipo": flagged, "sinais": flags_count}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de Wilson (95%) para uma proporção k/n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    centro = (p + z * z / (2 * n)) / (1 + z * z / n)
    meia = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return (max(0.0, centro - meia), min(1.0, centro + meia))


def to_markdown(result: dict) -> str:
    """Resumo legível dos resultados (gravado em docs/resultados/voice_baseline.md)."""
    lim = result["limiares"]
    cal, res = result["calibracao"], result["reservado"]
    lo, hi = wilson(res["algum_alarme"], res["n"])
    linhas = [
        "# Linha de base de voz e falsos alarmes (Common Voice pt-BR, T37 passo 9)", "",
        "Gerado por `scripts/evaluate_voice.py`. Os falantes foram divididos em calibração (linha de base) e "
        "reservado (nunca usado para ajustar nada). Todas as vozes são de pessoas que gravaram frases "
        "do Common Voice; nenhuma tem doença da fala conhecida, então só se mede **especificidade** "
        "(falsos alarmes), não sensibilidade.", "",
        f"Limiares em uso (`config/thresholds.yaml`, não alterados): {lim}.", "",
        "## Falsos alarmes em vozes saudáveis", "",
        "| Grupo | Falantes | Com algum alarme | Taxa | `voice_fatigue` | `voice_dysarthria_indicator` |",
        "|---|---|---|---|---|---|",
        f"| Calibração (a própria linha de base; otimista) | {cal['n']} | {cal['algum_alarme']} | "
        f"{cal['taxa']:.1%} | {cal['por_tipo']['voice_fatigue']} | {cal['por_tipo']['voice_dysarthria_indicator']} |",
        f"| **Reservado** | {res['n']} | {res['algum_alarme']} | **{res['taxa']:.1%}** "
        f"(IC 95%: {lo:.0%} a {hi:.0%}) | {res['por_tipo']['voice_fatigue']} | "
        f"{res['por_tipo']['voice_dysarthria_indicator']} |", "",
        f"Sinais que dispararam no reservado: {res['sinais'] or 'nenhum'}. Na calibração: {cal['sinais'] or 'nenhum'}.", "",
        "## Distribuição das medidas (média, percentis 5 e 95)", "",
        "| Medida | Calibração | Reservado |", "|---|---|---|",
    ]
    for k in ("speech_rate_wpm", "pause_ratio", "jitter", "shimmer_db", "hnr", "loudness", "duration_s"):
        c, r = result["distribuicao"]["calibracao"][k], result["distribuicao"]["reservado"][k]
        linhas.append(f"| `{k}` | {c['media']} ({c['p5']} a {c['p95']}) | {r['media']} ({r['p5']} a {r['p95']}) |")
    linhas += [
        "", "## Limitações", "",
        f"1. **Poucas vozes reservadas** ({res['n']}): cada falante pesa {1 / res['n']:.1%}; o intervalo de confiança é largo.",
        "2. **Estilo de leitura, não conversa.** Os falantes leem frases curtas (às vezes uma palavra). Voluntários "
        "saudáveis ficam entre os percentis 5 e 95 da velocidade de fala acima, então o limiar fixo de 100 palavras "
        "por minuto marca como lentos muitos leitores saudáveis, e o limiar de pausas (0,40) fica bem acima do que "
        "esse material mostra. Esses dois limiares **não foram calibrados com estes dados** e precisam de conversas reais.",
        "3. **Canal de gravação.** Os áudios são MP3 de microfones variados; jitter, shimmer e HNR dependem do canal. "
        "A linha de base só vale para áudio de qualidade parecida; gravações de consultas reais precisam de uma própria.",
        "4. **População.** O recorte tem muito mais homens (cerca de 71% dos clipes) e quase só adultos de 20 a 40 anos.",
        "5. **Sem vozes patológicas.** Detectar fadiga ou disartria de verdade exigiria fala patológica anotada "
        "(por exemplo, TORGO ou UA-Speech, com cadastro), que não foi usada.",
    ]
    return "\n".join(linhas) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cv-dir", type=Path, default=CV_DIR)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "resultados")
    ap.add_argument("--min-clips", type=int, default=10)
    ap.add_argument("--clips", type=int, default=10)
    args = ap.parse_args(argv)

    df = load_clips(args.cv_dir)
    speakers = select_speakers(df, args.min_clips, args.clips)
    print(f"{len(df)} clipes de {df['spk'].nunique()} falantes; {len(speakers)} com {args.min_clips}+ clipes")

    splits = load_splits().get("voice")
    if not splits:  # a divisão é gerada uma única vez e nunca refeita
        parts = split_ids(list(speakers), (2 / 3, 1 / 3), ("calibracao", "reservado"))
        rule = (f"falantes com {args.min_clips}+ clipes; {args.clips} clipes cada; "
                "2/3 calibração, 1/3 reservado")
        splits = {"dataset": "Common Voice pt-BR (recorte brasileiro, MDC)",
                  "unit": "falante (prefixo do client_id)", "rule": rule, **parts}
        save_section("voice", splits)

    rows: dict[str, list[dict]] = {"calibracao": [], "reservado": []}
    with tempfile.TemporaryDirectory() as tmp:
        for group in rows:
            for spk in splits[group]:
                if spk not in speakers:
                    continue
                wav = Path(tmp) / f"{spk}.wav"
                segs = make_sample(args.cv_dir, speakers[spk], wav)
                rows[group].append(extract_features(wav, segs, None))
    print({g: len(v) for g, v in rows.items()})

    baseline = baseline_from_rows(rows["calibracao"])
    ref = ROOT / "data" / "references" / "voice_baseline.json"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    cfg = load_yaml("thresholds")["voice"]
    result = {
        "limiares": cfg,
        "linha_de_base": baseline,
        "calibracao": evaluate(rows["calibracao"], baseline, cfg),
        "reservado": evaluate(rows["reservado"], baseline, cfg),
        "distribuicao": {g: {k: summarize(v, k) for k in ("speech_rate_wpm", "pause_ratio", "jitter",
                                                          "shimmer_db", "hnr", "loudness", "duration_s")}
                         for g, v in rows.items()},
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "voice_baseline.json").write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    (args.out / "voice_baseline.md").write_text(to_markdown(result), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("calibracao", "reservado")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
