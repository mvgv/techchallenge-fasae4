"""Gera data/references/voice_baseline.json a partir de gravações saudáveis."""
import argparse
import json
import statistics
from pathlib import Path

from medwatch.audio.acoustic import Z_FEATURES, extract_features


def baseline_from_rows(rows: list[dict]) -> dict:
    """Média e desvio de cada feature a partir de atributos já extraídos (um dict por gravação)."""
    baseline: dict = {}
    for f in Z_FEATURES + ("pause_ratio",):
        vals = [r[f] for r in rows if r.get(f) is not None]
        if vals:
            baseline[f] = {"mean": statistics.fmean(vals),
                           "std": statistics.pstdev(vals) if len(vals) > 1 else 0.0}
    return baseline


def build(wavs: list[Path]) -> dict:
    return baseline_from_rows([extract_features(w, [], None) for w in wavs])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True, help="WAVs de voz saudável")
    ap.add_argument("--output", default="data/references/voice_baseline.json")
    args = ap.parse_args()
    wavs = [Path(p) for p in args.input]
    baseline = build(wavs)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(baseline, indent=2))
    print(f"{len(wavs)} gravações -> {out}")


if __name__ == "__main__":
    main()
