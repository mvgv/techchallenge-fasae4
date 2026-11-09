"""Avaliação dos detectores de vitais em 30 pacientes sintéticos (seeds 100–129).

Roda o AnomalyWorker diretamente (sem Redis/banco) e compara três configurações:
NEWS2; NEWS2 + z-score; NEWS2 + z-score + Isolation Forest.
Uso: python scripts/evaluate_vitals.py [--out docs/resultados]
"""
from __future__ import annotations

import argparse
import csv
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path

from medwatch.anomaly.iforest import VitalsIForest
from medwatch.anomaly.worker import AnomalyWorker
from medwatch.simulator.synthetic import generate_patient_timeline

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
MINUTES = 24 * 60
TOLERANCE = timedelta(minutes=30)
PLAN = [("normal", 10), ("respiratory_deterioration", 5), ("hypotension", 5),
        ("tachy_spike", 5), ("sensor_artifact", 5)]
_NEWS = {"news2_low_medium", "news2_medium", "news2_high"}
CONFIGS = {
    "NEWS2": _NEWS,
    "NEWS2 + z-score": _NEWS | {"vital_zscore"},
    "NEWS2 + z-score + IForest": _NEWS | {"vital_zscore", "vital_iforest"},
}


class _NullDb:
    def insert_vital(self, *_a):
        pass


def _scenarios() -> list[tuple[int, str]]:
    out, seed = [], 100
    for sc, n in PLAN:
        for _ in range(n):
            out.append((seed, sc))
            seed += 1
    return out


def run_patient(seed: int, scenario: str, iforest: VitalsIForest):
    pid = f"E-{seed}"
    vitals, _rx, _mv, labels = generate_patient_timeline(pid, START, MINUTES, scenario, seed)
    worker = AnomalyWorker(bus=None, db_module=_NullDb(), iforest=iforest)  # type: ignore[arg-type]
    dets = []
    for v in vitals:
        for e in worker.process_vital(v):
            dets.append((e.ts_start, e.type))
    return vitals, labels, dets


def score_config(per_patient: list[tuple[list, list]], types: set[str]) -> dict:
    tp = fp = fn = 0
    delays: list[float] = []
    for labels, dets in per_patient:
        dets = [d for d in dets if d[1] in types]
        pos = [(datetime.fromisoformat(lb["ts_start"]), datetime.fromisoformat(lb["ts_end"]))
               for lb in labels if lb["type"] != "sensor_artifact"]
        for a, b in pos:
            hit = sorted(t for t, _ in dets if a <= t <= b + TOLERANCE)
            if hit:
                tp += 1
                delays.append((hit[0] - a).total_seconds() / 60)
            else:
                fn += 1
        fp += sum(1 for t, _ in dets if not any(a <= t <= b + TOLERANCE for a, b in pos))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec, "f1": f1,
            "median_delay_min": statistics.median(delays) if delays else float("nan"),
            "fp_per_patient_day": fp / len(per_patient)}


def example_plot(vitals, dets, path: Path, title: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(10, 6))
    ts = [v.ts for v in vitals]
    for ax, key, lab in zip(axes, ("hr", "spo2", "rr"), ("FC (bpm)", "SpO₂ (%)", "FR (irpm)"),
                           strict=True):
        ax.plot(ts, [getattr(v, key) for v in vitals], lw=0.8)
        ax.set_ylabel(lab)
    colors = {"vital_zscore": "tab:orange", "vital_iforest": "tab:green"}
    for t, typ in dets:
        for ax in axes:
            ax.axvline(t, color=colors.get(typ, "tab:red"), alpha=0.6, lw=0.8)
    axes[0].set_title(f"{title} — vermelho: NEWS2, laranja: z-score, verde: IForest")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/resultados")
    out = Path(ap.parse_args().out)
    out.mkdir(parents=True, exist_ok=True)

    iforest = VitalsIForest()
    iforest.load()
    if not iforest.enabled:
        print("AVISO: modelo IForest ausente (rode scripts/train_vitals_iforest.py); "
              "a 3ª configuração será igual à 2ª")
    per_patient, example = [], None
    for seed, sc in _scenarios():
        vitals, labels, dets = run_patient(seed, sc, iforest)
        per_patient.append((labels, dets))
        if sc == "respiratory_deterioration" and example is None:
            example = (vitals, dets, f"Paciente E-{seed} ({sc})")

    rows = [{"config": name, **score_config(per_patient, types)}
            for name, types in CONFIGS.items()]

    cols = ["config", "tp", "fp", "fn", "precision", "recall", "f1", "median_delay_min",
            "fp_per_patient_day"]
    with open(out / "vitals_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})

    md = ["# Avaliação dos vitais (30 pacientes sintéticos, seeds 100–129, 24 h)", "",
          "| Configuração | TP | FP | FN | Precisão | Recall | F1 | Atraso mediano (min) "
          "| FP/paciente-dia |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['config']} | {r['tp']} | {r['fp']} | {r['fn']} | {r['precision']:.2f} "
                  f"| {r['recall']:.2f} | {r['f1']:.2f} | {r['median_delay_min']:.1f} "
                  f"| {r['fp_per_patient_day']:.2f} |")
    md += ["", "Critério: detecção dentro de `[ts_start, ts_end + 30 min]` de um rótulo positivo "
           "(respiratory_deterioration, hypotension, tachy_spike) conta como um TP por rótulo; "
           "detecções fora dessas janelas são FP (inclui as causadas por `sensor_artifact`); "
           "rótulos sem detecção são FN.", "",
           "Leitura: o gerador mantém o estado alterado até o fim do dia e o worker repete "
           "alertas NEWS2 médio/alto a cada `repeat_minutes`; essas repetições após a janela "
           "do rótulo contam como FP. O z-score também dispara em pacientes normais "
           "(limiar/cooldown da `thresholds.yaml`).", ""]
    (out / "vitals_metrics.md").write_text("\n".join(md), encoding="utf-8")
    if example:
        v, d, title = example
        example_plot(v, d, out / "vitals_example.png", title)
    print("\n".join(md))


if __name__ == "__main__":
    main()
