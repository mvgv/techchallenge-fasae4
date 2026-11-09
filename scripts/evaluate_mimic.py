"""Avaliação dos detectores de vitais com dados reais do MIMIC-IV Demo (T37).

Carga de alarmes (sem rótulos): roda o AnomalyWorker e o FusionEngine offline em cada
internação dos pacientes de uma divisão de `config/splits.yaml` e mede o que a equipe médica
receberia: alertas por paciente-dia, distribuição por nível e frequência de NEWS2 alto.

Uso: python scripts/evaluate_mimic.py [--splits validacao reservado] [--out docs/resultados]
O Isolation Forest usado é `models/vitals_iforest_mimic` (scripts/train_vitals_iforest.py).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
from collections import Counter
from datetime import timedelta
from pathlib import Path

from medwatch.anomaly.filters import clean_observation
from medwatch.anomaly.iforest import VitalsIForest
from medwatch.anomaly.news2 import news2
from medwatch.anomaly.worker import AnomalyWorker
from medwatch.config import load_yaml
from medwatch.simulator.mimic import frames_to_models, load_mimic_frames

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("evaluate_vitals",
                                               ROOT / "scripts" / "evaluate_vitals.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)

STAY_GAP = timedelta(hours=12)       # lacuna maior que isso separa internações
MODEL = "vitals_iforest_mimic"
RX_TYPES_PREFIX = "rx_"
CONFIGS = {**ev.CONFIGS, "Todos (vitais + prescrições)": None}   # None = todos os tipos


class NullDb:
    """Banco nulo: o worker grava vitais e prescrições, aqui descartados."""

    def insert_vital(self, *_a):
        pass

    def insert_prescription(self, *_a):
        pass


def segments(vitals: list, rx: list) -> list[tuple[list, list]]:
    """Divide as séries de um paciente em internações (lacuna > 12 h entre vitais).

    Cada prescrição vai para a internação em que cai (de 12 h antes do início até o fim).
    """
    segs: list[list] = []
    for v in vitals:
        if not segs or v.ts - segs[-1][-1].ts > STAY_GAP:
            segs.append([])
        segs[-1].append(v)
    out = []
    for s in segs:
        a, b = s[0].ts - STAY_GAP, s[-1].ts
        out.append((s, [e for e in rx if a <= e.ts <= b]))
    return out


def stay_days(vitals: list) -> float:
    """Duração da internação em dias (mínimo de 1 hora)."""
    return max((vitals[-1].ts - vitals[0].ts).total_seconds(), 3600) / 86400


def run_stay(vitals: list, rx: list, iforest: VitalsIForest | None, cfg: dict) -> list:
    """Roda o worker numa internação (vitais e prescrições em ordem de tempo)."""
    worker = AnomalyWorker(bus=None, db_module=NullDb(),  # type: ignore[arg-type]
                           iforest=iforest, cfg=cfg)
    items = sorted([(v.ts, 0, v) for v in vitals] + [(e.ts, 1, e) for e in rx],
                   key=lambda x: (x[0], x[1]))
    evs = []
    for _ts, kind, obj in items:
        evs += worker.process_vital(obj) if kind == 0 else worker.process_rx(obj)
    return evs


def _filter(evs: list, types: set[str] | None) -> list:
    return list(evs) if types is None else [e for e in evs if e.type in types]


def load_split(split: str):
    """Pacientes da divisão como lista de (patient_id, vitais, prescrições)."""
    vdf, rdf = load_mimic_frames(None, split=split)
    vitals, rx = frames_to_models(vdf, rdf)
    by_v: dict[str, list] = {}
    by_r: dict[str, list] = {}
    for v in vitals:
        by_v.setdefault(v.patient_id, []).append(v)
    for e in rx:
        by_r.setdefault(e.patient_id, []).append(e)
    return [(pid, by_v[pid], by_r.get(pid, [])) for pid in sorted(by_v)]


def alarm_load(split: str, iforest: VitalsIForest | None, cfg: dict, fusion_cfg: dict) -> dict:
    """Carga de alarmes numa divisão: por configuração, nível e exemplos."""
    bounds = cfg["vitals"]["physiologic_bounds"]
    stays = []
    n_obs = n_high = n_med = 0
    for pid, vitals, rx in load_split(split):
        for k, (sv, srx) in enumerate(segments(vitals, rx)):
            evs = run_stay(sv, srx, iforest, cfg)
            stays.append({"patient_id": pid, "stay": k, "vitals": sv, "evs": evs,
                          "days": stay_days(sv)})
            for v in sv:
                total = news2(clean_observation(v, bounds)[0])["total"]
                n_obs += 1
                n_high += total >= 7
                n_med += total >= 5
    days = sum(s["days"] for s in stays)
    out = {"split": split, "patients": len({s["patient_id"] for s in stays}),
           "stays": len(stays), "patient_days": days, "observations": n_obs,
           "news2_high_frac": n_high / max(n_obs, 1),
           "news2_medium_or_more_frac": n_med / max(n_obs, 1),
           "evidence_by_type": dict(Counter(e.type for s in stays for e in s["evs"])),
           "configs": {}}
    for name, types in CONFIGS.items():
        levels: Counter = Counter()
        n = 0
        per_stay = []
        for s in stays:
            al = ev.alert_details(_filter(s["evs"], types), fusion_cfg)
            n += len(al)
            levels.update(a["level"] for a in al)
            per_stay.append(len(al))
            if types is None:
                s["alerts"] = al
        out["configs"][name] = {
            "alerts": n, "alerts_per_patient_day": n / max(days, 1e-9),
            "by_level": dict(levels),
            "stays_with_alert": sum(1 for x in per_stay if x),
        }
    out["examples"] = examples(stays)
    return out


def _vitals_at(vitals: list, t) -> dict:
    prev = [v for v in vitals if v.ts <= t] or vitals[:1]
    v = prev[-1]
    return {k: getattr(v, k) for k in ("hr", "sbp", "spo2", "rr", "temp")}


def examples(stays: list, n: int = 3) -> list[dict]:
    """Até `n` alertas variados: o crítico de maior risco, um de aviso e um de outro tipo."""
    cands = [(s, a) for s in stays for a in s.get("alerts", [])]
    chosen: list[tuple] = []
    crit = sorted((c for c in cands if c[1]["level"] == "critical"),
                  key=lambda c: -c[1]["peak_risk"])
    warn = sorted((c for c in cands if c[1]["level"] == "warning"),
                  key=lambda c: -c[1]["peak_risk"])
    for pool in (crit, warn):
        if pool:
            chosen.append(pool[0])
    used = {tuple(c[1]["types"][:1]) for c in chosen}
    for c in crit[1:] + warn[1:]:
        if len(chosen) >= n:
            break
        if tuple(c[1]["types"][:1]) not in used and c[0]["patient_id"] not in {
                x[0]["patient_id"] for x in chosen}:
            chosen.append(c)
            used.add(tuple(c[1]["types"][:1]))
    out = []
    for s, a in chosen[:n]:
        hours = (a["opened"] - s["vitals"][0].ts).total_seconds() / 3600
        dur = (((a["closed"] or s["vitals"][-1].ts) - a["opened"]).total_seconds() / 3600)
        out.append({"patient_id": s["patient_id"], "stay": s["stay"],
                    "hours_into_stay": round(hours, 1), "duration_h": round(dur, 1),
                    "level": a["level"], "peak_risk": a["peak_risk"], "types": a["types"],
                    "vitals_at_open": _vitals_at(s["vitals"], a["opened"])})
    return out


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%".replace(".", ",")


def _f(x: float, d: int = 2) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def load_markdown(res: list[dict]) -> list[str]:
    """Seção de carga de alarmes do relatório."""
    md = ["## Carga de alarmes em dados reais (sem rótulos)", "",
          "Cada internação (lacuna de mais de 12 h entre vitais separa internações) passa pelo "
          "`AnomalyWorker` e pelo `FusionEngine`; um alerta abre com nível `warning` ou mais e "
          "fecha após 60 min seguidos com risco abaixo de 20 (mesma regra da T36). "
          f"Isolation Forest: `{MODEL}`.", ""]
    md += ["| Divisão | Pacientes | Internações | Paciente-dias | Leituras | NEWS2 ≥ 5 "
           "| NEWS2 ≥ 7 (alto) |", "|---|---|---|---|---|---|---|"]
    for r in res:
        md.append(f"| {r['split']} | {r['patients']} | {r['stays']} | {_f(r['patient_days'], 1)} "
                  f"| {r['observations']} | {_pct(r['news2_medium_or_more_frac'])} "
                  f"| {_pct(r['news2_high_frac'])} |")
    md += ["", "| Divisão | Configuração | Alertas | Alertas/paciente-dia | Crítico | Aviso "
           "| Internações com alerta |", "|---|---|---|---|---|---|---|"]
    for r in res:
        for name, c in r["configs"].items():
            md.append(f"| {r['split']} | {name} | {c['alerts']} "
                      f"| {_f(c['alerts_per_patient_day'])} | {c['by_level'].get('critical', 0)} "
                      f"| {c['by_level'].get('warning', 0)} "
                      f"| {c['stays_with_alert']}/{r['stays']} |")
    md += ["", "Evidências por tipo:", ""]
    for r in res:
        items = ", ".join(f"`{k}` {v}" for k, v in sorted(r["evidence_by_type"].items(),
                                                          key=lambda x: -x[1]))
        md.append(f"- {r['split']}: {items}")
    md += ["", "Exemplos (configuração completa):", ""]
    for r in res:
        for e in r["examples"]:
            v = e["vitals_at_open"]
            vit = ", ".join(f"{k.upper()} {_f(x, 0) if k != 'temp' else _f(x, 1)}"
                            for k, x in v.items() if x is not None)
            md.append(f"- {r['split']}, `{e['patient_id']}` (internação {e['stay']}): alerta "
                      f"`{e['level']}` com {_f(e['hours_into_stay'], 1)} h de internação, "
                      f"risco de pico {_f(e['peak_risk'], 0)}, duração {_f(e['duration_h'], 1)} h; "
                      f"evidências principais: {', '.join(e['types'])}; na abertura: {vit}.")
    return md + [""]


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--splits", nargs="+", default=["validacao", "reservado"])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "resultados")
    a = ap.parse_args(argv)
    iforest = VitalsIForest(model_name=MODEL)
    if not iforest.load():
        print(f"AVISO: {MODEL} ausente; rode train_vitals_iforest.py --mimic-split calibracao")
    cfg, fusion_cfg = load_yaml("thresholds"), load_yaml("fusion")
    res = [alarm_load(s, iforest if iforest.enabled else None, cfg, fusion_cfg)
           for s in a.splits]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "mimic_alarm_load.json").write_text(
        json.dumps(res, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    md = load_markdown(res)
    (a.out / "mimic_alarm_load.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    _ = statistics  # usado na parte semissintética


if __name__ == "__main__":
    main()
