"""Avaliação dos detectores de vitais em 30 pacientes sintéticos (seeds 100–129).

Roda o AnomalyWorker diretamente (sem Redis/banco) e compara três configurações:
NEWS2; NEWS2 + z-score; NEWS2 + z-score + Isolation Forest, em três níveis de métrica:
por evidência, por episódio e por alerta (evidências passadas pelo FusionEngine).

Uso: python scripts/evaluate_vitals.py [--out docs/resultados] [--tune] [--seed-base 100]
`--tune` roda a grade de limiares (z-score × persistência × IForest × persistência) e grava
`vitals_tuning.md`; os valores escolhidos ficam em `config/thresholds.yaml`.
"""
from __future__ import annotations

import argparse
import copy
import csv
import itertools
import statistics
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from medwatch.anomaly.filters import clean_observation
from medwatch.anomaly.iforest import VitalsIForest, build_features
from medwatch.anomaly.worker import AnomalyWorker
from medwatch.config import load_yaml
from medwatch.fusion.engine import FusionEngine
from medwatch.simulator.synthetic import generate_patient_timeline

START = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
MINUTES = 24 * 60
TOLERANCE = timedelta(minutes=30)
EPISODE_GAP = timedelta(minutes=30)
CLOSE_RISK, CLOSE_MINUTES = 20.0, 60
OPEN_LEVELS = ("warning", "critical")
PLAN = [("normal", 10), ("respiratory_deterioration", 5), ("hypotension", 5),
        ("tachy_spike", 5), ("sensor_artifact", 5)]
_NEWS = {"news2_low_medium", "news2_medium", "news2_high"}
CONFIGS = {
    "NEWS2": _NEWS,
    "NEWS2 + z-score": _NEWS | {"vital_zscore"},
    "NEWS2 + z-score + IForest": _NEWS | {"vital_zscore", "vital_iforest"},
}
FULL = "NEWS2 + z-score + IForest"


class _NullDb:
    def insert_vital(self, *_a):
        pass


class CachedIForest(VitalsIForest):
    """Isolation Forest com cache do score bruto: a grade de limiares reaproveita os scores."""

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[bytes, float] = {}

    def raw_score(self, features) -> float:
        key = features.tobytes()
        if key not in self._cache:
            self._cache[key] = super().raw_score(features)
        return self._cache[key]

    def prefill(self, vitals: list, bounds: dict) -> None:
        """Calcula em lote os scores de todas as janelas de uma série (após o filtro)."""
        if not self.enabled:
            return
        clean = [clean_observation(v, bounds)[0] for v in vitals]
        feats = {}
        for i in range(5, len(clean)):
            f = build_features(clean[i - 5:i + 1])
            if f is not None and f.tobytes() not in self._cache:
                feats[f.tobytes()] = f
        if feats:
            scores = self.pipeline.score_samples(np.vstack(list(feats.values())))
            self._cache.update(zip(feats, map(float, scores), strict=True))


def _scenarios(seed_base: int = 100) -> list[tuple[int, str]]:
    out, seed = [], seed_base
    for sc, n in PLAN:
        for _ in range(n):
            out.append((seed, sc))
            seed += 1
    return out


_TIMELINES: dict[tuple[int, str], tuple] = {}


def timeline(seed: int, scenario: str):
    """(vitais, rótulos) de um paciente, gerados uma vez só."""
    if (seed, scenario) not in _TIMELINES:
        vitals, _rx, _mv, labels = generate_patient_timeline(
            f"E-{seed}", START, MINUTES, scenario, seed)
        _TIMELINES[(seed, scenario)] = (vitals, labels)
    return _TIMELINES[(seed, scenario)]


def run_patient(seed: int, scenario: str, iforest: VitalsIForest, cfg: dict | None = None):
    """Roda o worker numa série; devolve (vitais, rótulos, detecções, evidências)."""
    vitals, labels = timeline(seed, scenario)
    worker = AnomalyWorker(bus=None, db_module=_NullDb(),  # type: ignore[arg-type]
                           iforest=iforest, cfg=cfg)
    dets, evs = [], []
    for v in vitals:
        for e in worker.process_vital(v):
            dets.append((e.ts_start, e.type))
            evs.append(e)
    return vitals, labels, dets, evs


def _positives(labels: list[dict]) -> list[tuple[datetime, datetime]]:
    return [(datetime.fromisoformat(lb["ts_start"]), datetime.fromisoformat(lb["ts_end"]))
            for lb in labels if lb["type"] != "sensor_artifact"]


def score_config(per_patient: list[tuple[list, list]], types: set[str]) -> dict:
    """Métrica por evidência: cada detecção fora das janelas de rótulo é um FP."""
    tp = fp = fn = 0
    delays: list[float] = []
    for labels, dets in per_patient:
        dets = [d for d in dets if d[1] in types]
        pos = _positives(labels)
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


def _summary(tp: int, fp: int, fn: int, delays: list[float], fp_normal: int,
             n_normal: int) -> dict:
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": prec, "recall": rec,
            "median_delay_min": statistics.median(delays) if delays else float("nan"),
            "fp_normal": fp_normal, "fp_normal_per_day": fp_normal / max(n_normal, 1)}


def score_episodes(per_patient: list[tuple[list, list]], types: set[str]) -> dict:
    """Métrica por episódio: TP por rótulo; FP = episódios fora das janelas de rótulo.

    Fora das janelas, detecções do mesmo tipo com menos de 30 min entre si formam um episódio.
    Os falsos alarmes dos pacientes `normal` (sem rótulos) são reportados à parte.
    """
    tp = fn = fp = fp_normal = n_normal = 0
    delays: list[float] = []
    for labels, dets in per_patient:
        dets = [d for d in dets if d[1] in types]
        pos = _positives(labels)
        for a, b in pos:
            hit = sorted(t for t, _ in dets if a <= t <= b + TOLERANCE)
            if hit:
                tp += 1
                delays.append((hit[0] - a).total_seconds() / 60)
            else:
                fn += 1
        outside = [d for d in dets if not any(a <= d[0] <= b + TOLERANCE for a, b in pos)]
        n_ep = 0
        for typ in {t for _, t in outside}:
            last = None
            for t in sorted(t for t, ty in outside if ty == typ):
                if last is None or t - last >= EPISODE_GAP:
                    n_ep += 1
                last = t
        fp += n_ep
        if not labels:
            fp_normal += n_ep
            n_normal += 1
    return _summary(tp, fp, fn, delays, fp_normal, n_normal)


def alert_details(evs: list, fusion_cfg: dict) -> list[dict]:
    """Alertas abertos a partir das evidências de um paciente, com nível e risco de pico.

    Nível >= warning abre; o alerta fecha quando o risco fica abaixo de 20 por 60 minutos
    seguidos. O risco é recalculado a cada minuto (decai sem novas evidências). Cada item:
    `opened`, `closed`, `level` (o maior durante o alerta), `peak_risk` e `types` (tipos de
    evidência que mais contribuíram no pico).
    """
    if not evs:
        return []
    engine = FusionEngine(fusion_cfg)
    pid = evs[0].patient_id
    by_min: dict[datetime, list] = {}
    for e in evs:
        by_min.setdefault(e.ts_start.replace(second=0, microsecond=0), []).append(e)
    t, last = min(by_min), max(by_min)
    alerts: list[dict] = []
    cur: dict | None = None
    below = 0
    while t <= last + timedelta(minutes=CLOSE_MINUTES + 1):
        for e in by_min.get(t, []):
            engine.add(e)
        res = engine.compute(pid, t)
        if cur is None:
            if res.level in OPEN_LEVELS:
                cur = {"opened": t, "closed": None, "level": res.level,
                       "peak_risk": res.risk, "types": _top_types(res)}
                alerts.append(cur)
                below = 0
        else:
            if res.level == "critical":
                cur["level"] = "critical"
            if res.risk > cur["peak_risk"]:
                cur["peak_risk"], cur["types"] = res.risk, _top_types(res)
            below = below + 1 if res.risk < CLOSE_RISK else 0
            if below >= CLOSE_MINUTES:
                cur["closed"], cur, below = t, None, 0
        t += timedelta(minutes=1)
    return alerts


def _top_types(res) -> list[str]:
    seen: list[str] = []
    for c in res.contributions:
        typ = c.get("type")
        if typ and typ not in seen:
            seen.append(typ)
    return seen[:3]


def alerts_from_evidence(evs: list, fusion_cfg: dict) -> list[datetime]:
    """Instantes de abertura de alertas (ver `alert_details`)."""
    return [a["opened"] for a in alert_details(evs, fusion_cfg)]


def score_alerts(per_patient: list[tuple[list, list]], fusion_cfg: dict) -> dict:
    """Métrica por alerta; `per_patient` traz (rótulos, evidências já filtradas por tipo)."""
    tp = fn = fp = fp_normal = n_normal = 0
    delays: list[float] = []
    for labels, evs in per_patient:
        opens = alerts_from_evidence(evs, fusion_cfg)
        pos = _positives(labels)
        for a, b in pos:
            hit = [t for t in opens if a <= t <= b + TOLERANCE]
            if hit:
                tp += 1
                delays.append((hit[0] - a).total_seconds() / 60)
            else:
                fn += 1
        n_fp = sum(1 for t in opens if not any(a <= t <= b + TOLERANCE for a, b in pos))
        fp += n_fp
        if not labels:
            fp_normal += n_fp
            n_normal += 1
    return _summary(tp, fp, fn, delays, fp_normal, n_normal)


def evaluate_all(seed_base: int, iforest: VitalsIForest, cfg: dict, fusion_cfg: dict,
                 configs: dict[str, set[str]] | None = None):
    """Roda o worker em todos os pacientes; devolve as três métricas por configuração."""
    configs = configs or CONFIGS
    runs = [(sc, *run_patient(seed, sc, iforest, cfg)) for seed, sc in _scenarios(seed_base)]
    rows = []
    for name, types in configs.items():
        rows.append({
            "config": name,
            "evidence": score_config([(lb, d) for _sc, _v, lb, d, _e in runs], types),
            "episode": score_episodes([(lb, d) for _sc, _v, lb, d, _e in runs], types),
            "alert": score_alerts(
                [(lb, [e for e in es if e.type in types]) for _sc, _v, lb, _d, es in runs],
                fusion_cfg)})
    return rows, runs


def with_params(cfg: dict, z_thr: float, z_pers: int, if_key: str, if_pers: int) -> dict:
    out = copy.deepcopy(cfg)
    out["vitals"]["zscore"].update(threshold=z_thr, persistence=z_pers)
    out["vitals"]["iforest"].update(threshold_key=if_key, persistence=if_pers)
    return out


def tune(seed_base: int, iforest: CachedIForest, base_cfg: dict, fusion_cfg: dict) -> list[dict]:
    """Grade completa: z-score (limiar × persistência) × IForest (limiar × persistência)."""
    for seed, sc in _scenarios(seed_base):
        iforest.prefill(timeline(seed, sc)[0], base_cfg["vitals"]["physiologic_bounds"])
    grid = []
    for zt, zp, ik, ip in itertools.product((3.0, 3.5, 4.0), (1, 3), ("threshold", "p0_1"),
                                            (1, 3)):
        rows, _ = evaluate_all(seed_base, iforest, with_params(base_cfg, zt, zp, ik, ip),
                               fusion_cfg, {FULL: CONFIGS[FULL]})
        r = rows[0]
        grid.append({"z_threshold": zt, "z_persistence": zp, "if_key": ik,
                     "if_persistence": ip, "alert": r["alert"], "episode": r["episode"]})
        print(f"z={zt}/{zp} if={ik}/{ip}: recall={r['alert']['recall']:.2f} "
              f"normal/dia={r['alert']['fp_normal_per_day']:.2f}", flush=True)
    return grid


def tuning_markdown(grid: list[dict], seed_base: int, title: str) -> list[str]:
    md = [f"## {title} (seeds {seed_base}–{seed_base + 29})", "",
          "| z limiar | z pers. | IForest limiar | IF pers. | TP | FN | Recall | Alertas FP "
          "| Alertas/dia (normais) | Precisão | Atraso mediano (min) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for g in grid:
        a = g["alert"]
        thr = "percentil 0,5" if g["if_key"] == "threshold" else "percentil 0,1"
        md.append(f"| {g['z_threshold']:.1f} | {g['z_persistence']} | {thr} "
                  f"| {g['if_persistence']} | {a['tp']} | {a['fn']} | {a['recall']:.2f} "
                  f"| {a['fp']} | {a['fp_normal_per_day']:.2f} | {a['precision']:.2f} "
                  f"| {a['median_delay_min']:.1f} |")
    return md + [""]


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


def _fmt(x: float) -> str:
    return "—" if x != x else f"{x:.1f}"


def results_markdown(rows: list[dict], seed_base: int, cfg: dict) -> list[str]:
    z, i = cfg["vitals"]["zscore"], cfg["vitals"]["iforest"]
    md = [f"# Avaliação dos vitais (30 pacientes sintéticos, seeds {seed_base}–"
          f"{seed_base + 29}, 24 h)", "",
          f"Limiares em uso: z-score {z['threshold']} com persistência "
          f"{z.get('persistence', 1)}; Isolation Forest `{i.get('threshold_key', 'threshold')}` "
          f"com persistência {i.get('persistence', 1)} (`config/thresholds.yaml`).", ""]
    head = ("| Configuração | TP | FP | FN | Precisão | Recall | Atraso mediano (min) "
            "| {extra} |\n|---|---|---|---|---|---|---|---|")
    md += ["## 1. Por alerta (número principal: o que a equipe médica veria)", "",
           "Evidências de cada paciente passam pelo `FusionEngine` (`config/fusion.yaml`); "
           "um alerta abre quando o nível chega a `warning` ou mais e fecha quando o risco "
           "fica abaixo de 20 por 60 minutos seguidos. TP: alerta aberto em "
           "`[ts_start, ts_end + 30 min]` de um rótulo positivo; os demais alertas são FP "
           "(inclui os causados por `sensor_artifact`).", "",
           head.format(extra="Alertas/dia em pacientes normais")]
    for r in rows:
        a = r["alert"]
        md.append(f"| {r['config']} | {a['tp']} | {a['fp']} | {a['fn']} | {a['precision']:.2f} "
                  f"| {a['recall']:.2f} | {_fmt(a['median_delay_min'])} "
                  f"| {a['fp_normal_per_day']:.2f} |")
    md += ["", "## 2. Por episódio", "",
           "TP: ao menos uma detecção em `[ts_start, ts_end + 30 min]`. Fora das janelas, "
           "detecções do mesmo tipo com menos de 30 min entre si formam um episódio, e cada "
           "episódio é um FP. Coluna final: episódios falsos por paciente-dia nos pacientes "
           "`normal`.", "", head.format(extra="Episódios FP/dia em normais")]
    for r in rows:
        a = r["episode"]
        md.append(f"| {r['config']} | {a['tp']} | {a['fp']} | {a['fn']} | {a['precision']:.2f} "
                  f"| {a['recall']:.2f} | {_fmt(a['median_delay_min'])} "
                  f"| {a['fp_normal_per_day']:.2f} |")
    md += ["", "## 3. Por evidência (método da T31, para comparação)", "",
           "Cada detecção fora das janelas de rótulo é um FP (repetições incluídas).", "",
           "| Configuração | TP | FP | FN | Precisão | Recall | F1 | Atraso mediano (min) "
           "| FP/paciente-dia |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a = r["evidence"]
        md.append(f"| {r['config']} | {a['tp']} | {a['fp']} | {a['fn']} | {a['precision']:.2f} "
                  f"| {a['recall']:.2f} | {a['f1']:.2f} | {_fmt(a['median_delay_min'])} "
                  f"| {a['fp_per_patient_day']:.2f} |")
    md += ["", "Rótulos: `respiratory_deterioration` e `hypotension` vão até o fim da série "
           "(o estado alterado persiste); `tachy_spike` dura 3 minutos.", ""]
    return md


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/resultados")
    ap.add_argument("--seed-base", type=int, default=100)
    ap.add_argument("--tune", action="store_true", help="roda a grade de limiares")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    iforest = CachedIForest()
    iforest.load()
    if not iforest.enabled:
        print("AVISO: modelo IForest ausente (rode scripts/train_vitals_iforest.py); "
              "a 3ª configuração será igual à 2ª")
    cfg, fusion_cfg = load_yaml("thresholds"), load_yaml("fusion")
    bounds = cfg["vitals"]["physiologic_bounds"]

    if args.tune:
        md = ["# Busca de limiares dos vitais (T36)", "",
              "Avaliação no nível de alerta (configuração NEWS2 + z-score + IForest); critério "
              "de escolha: recall de 100% nos rótulos positivos e menor número de alertas em "
              "pacientes normais. Os 30 pacientes de ajuste (`seeds 100–129`) e os 30 de "
              "conferência (`seeds 200–229`, nunca usados no ajuste) têm a mesma composição.", ""]
        for base, title in ((100, "Ajuste"), (200, "Conferência")):
            for sd, sc in _scenarios(base):
                iforest.prefill(timeline(sd, sc)[0], bounds)
            grid = tune(base, iforest, cfg, fusion_cfg)
            md += tuning_markdown(grid, base, title)
            (out / f"vitals_tuning_{base}.md").write_text("\n".join(md), encoding="utf-8")
        (out / "vitals_tuning.md").write_text("\n".join(md), encoding="utf-8")
        return

    for sd, sc in _scenarios(args.seed_base):
        if isinstance(iforest, CachedIForest):
            iforest.prefill(timeline(sd, sc)[0], bounds)
    rows, runs = evaluate_all(args.seed_base, iforest, cfg, fusion_cfg)

    cols = ["config", "level", "tp", "fp", "fn", "precision", "recall", "median_delay_min",
            "fp_normal_per_day", "fp_per_patient_day"]
    with open(out / "vitals_metrics.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            for level in ("alert", "episode", "evidence"):
                m = r[level]
                w.writerow({"config": r["config"], "level": level,
                            **{k: (round(m[k], 3) if isinstance(m[k], float) else m[k])
                               for k in cols[2:7]},
                            **{k: round(m[k], 3) for k in cols[7:] if k in m}})
    md = results_markdown(rows, args.seed_base, cfg)
    (out / "vitals_metrics.md").write_text("\n".join(md), encoding="utf-8")
    for sc, vitals, _lb, dets, _e in runs:
        if sc == "respiratory_deterioration":
            example_plot(vitals, dets, out / "vitals_example.png",
                         f"Paciente {vitals[0].patient_id} ({sc})")
            break
    print("\n".join(md))


if __name__ == "__main__":
    main()
