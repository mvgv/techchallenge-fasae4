"""Treina o Isolation Forest de vitais com pacientes sintéticos normais."""
import argparse
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from medwatch.anomaly.iforest import features_from_series, train_and_save
from medwatch.config import get_settings
from medwatch.simulator.synthetic import generate_patient_timeline


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mimic", action="store_true", help="inclui 50%% das observações do MIMIC")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[np.ndarray] = []
    for seed in range(1, 21):
        vitals, *_ = generate_patient_timeline(f"T-{seed:03d}", start, 48 * 60, "normal", seed)
        rows += features_from_series(vitals)
    if args.mimic:
        from medwatch.simulator.mimic import load_mimic

        vitals, _ = load_mimic(1000)
        by_patient = defaultdict(list)
        for v in vitals:
            by_patient[v.patient_id].append(v)
        for series in by_patient.values():
            rows += features_from_series(series[: len(series) // 2])
    meta = train_and_save(np.vstack(rows), args.out or get_settings().models_dir)
    print(meta)


if __name__ == "__main__":
    main()
