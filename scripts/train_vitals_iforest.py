"""Treina o Isolation Forest de vitais.

Padrão: pacientes sintéticos normais (1 leitura/min) → models/vitals_iforest.
Dados reais: --mimic-split calibracao [--val-split validacao] → models/vitals_iforest_mimic,
com os limiares calculados na validação. O worker escolhe o modelo por VITALS_IFOREST_MODEL.
"""
import argparse
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from medwatch.anomaly.iforest import MODEL_NAME, features_from_series, train_and_save
from medwatch.config import get_settings
from medwatch.simulator.synthetic import generate_patient_timeline


def mimic_features(split: str | None, limit: int | None = None,
                   first_half: bool = False, carry_forward: bool = False) -> list[np.ndarray]:
    """Features de cada paciente do MIMIC na divisão `split` (série inteira ou 1ª metade)."""
    from medwatch.simulator.mimic import load_mimic

    vitals, _ = load_mimic(limit, split=split)
    by_patient = defaultdict(list)
    for v in vitals:
        by_patient[v.patient_id].append(v)
    rows: list[np.ndarray] = []
    for series in by_patient.values():
        rows += features_from_series(series[: len(series) // 2] if first_half else series,
                                     carry_forward)
    return rows


def resolve_out(out: Path | None, default_name: str) -> tuple[Path, str]:
    """`--out` pode ser um diretório ou um prefixo `dir/vitals_iforest_xxx`."""
    if out is None:
        return get_settings().models_dir, default_name
    if out.name.startswith(MODEL_NAME):
        return out.parent, out.name
    return out, default_name


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mimic", action="store_true",
                    help="sintético + 50%% das observações do MIMIC (modo antigo)")
    ap.add_argument("--mimic-split", help="treina só com esta divisão do MIMIC")
    ap.add_argument("--val-split", default="validacao",
                    help="divisão do MIMIC usada para os limiares (com --mimic-split)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    if args.mimic_split:
        X = np.vstack(mimic_features(args.mimic_split, carry_forward=True))
        X_val = (np.vstack(mimic_features(args.val_split, carry_forward=True))
                 if args.val_split else None)
        out_dir, name = resolve_out(args.out, f"{MODEL_NAME}_mimic")
        meta = train_and_save(X, out_dir, name, X_val, {
            "source": f"mimic:{args.mimic_split}", "carry_forward": True,
            "thresholds_from": f"mimic:{args.val_split}" if args.val_split else "treino"})
        print(name, meta)
        return
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[np.ndarray] = []
    for seed in range(1, 21):
        vitals, *_ = generate_patient_timeline(f"T-{seed:03d}", start, 48 * 60, "normal", seed)
        rows += features_from_series(vitals)
    if args.mimic:
        rows += mimic_features(None, 1000, first_half=True)
    out_dir, name = resolve_out(args.out, MODEL_NAME)
    meta = train_and_save(np.vstack(rows), out_dir, name,
                          extra_meta={"source": "synthetic" + ("+mimic" if args.mimic else "")})
    print(name, meta)


if __name__ == "__main__":
    main()
