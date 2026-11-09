"""Avaliação dos detectores de vitais com dados reais do MIMIC-IV Demo (T37).

1. Carga de alarmes (sem rótulos): roda o AnomalyWorker e o FusionEngine offline em cada
   internação dos pacientes de uma divisão de `config/splits.yaml` e mede o que a equipe médica
   receberia: alertas por paciente-dia, distribuição por nível e frequência de NEWS2 alto.
2. Recall semissintético: injeta os cenários conhecidos (`respiratory_deterioration`,
   `hypotension`, `tachy_spike`) por cima das séries reais, com as mesmas magnitudes do gerador
   sintético, e mede precisão, recall e atraso no nível de alerta.

Uso:
  python scripts/evaluate_mimic.py --tune            # grade do IForest na validação
  python scripts/evaluate_mimic.py                   # validação e reservado, limiares do YAML
O Isolation Forest usado é `models/vitals_iforest_mimic` (scripts/train_vitals_iforest.py).
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import itertools
import json
import random
import statistics
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from medwatch.anomaly.filters import clean_observation
from medwatch.anomaly.iforest import VitalsIForest, build_features
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


# --------------------------------------------------------------------------------------
# Parte semissintética: cenários conhecidos injetados por cima das séries reais
# --------------------------------------------------------------------------------------

INJECTED = ("respiratory_deterioration", "hypotension", "tachy_spike")
# Mesmas magnitudes do gerador sintético (synthetic.py), aplicadas como deslocamento sobre o
# valor real; não foram ajustadas (nem na validação nem no reservado).
RESP_RAMP_MIN, RESP_DELTA = 60, {"spo2": -10.0, "rr": 13.0, "hr": 40.0}
HYPO_RAMP_MIN, HYPO_SBP_TARGET, HYPO_HR_DELTA = 45, 82.0, 25.0
TACHY_HR, TACHY_MIN = 155.0, 3
MIN_STAY_H, MARGIN_H = 12, 6      # internação mínima e margem do sorteio do início
SEED = 42
FULL_TYPES = ev.CONFIGS[ev.FULL]


class CachedIForest(VitalsIForest):
    """IForest do MIMIC com cache do score bruto (a grade reaproveita os scores)."""

    def __init__(self) -> None:
        super().__init__(model_name=MODEL)
        self._cache: dict[bytes, float] = {}

    def raw_score(self, features) -> float:
        key = np.asarray(features, dtype=float).tobytes()
        if key not in self._cache:
            self._cache[key] = super().raw_score(features)
        return self._cache[key]


def _ramp_frac(t: datetime, onset: datetime, minutes: int) -> float:
    return min(max((t - onset).total_seconds() / 60 / minutes, 0.0), 1.0)


def inject(vitals: list, scenario: str, onset: datetime) -> tuple[list, dict]:
    """Copia a série com o cenário aplicado a partir de `onset`; devolve (série, rótulo)."""
    out = []
    end = vitals[-1].ts
    if scenario == "respiratory_deterioration":
        for v in vitals:
            if v.ts < onset:
                out.append(v)
                continue
            f = _ramp_frac(v.ts, onset, RESP_RAMP_MIN)
            upd = {k: (None if getattr(v, k) is None else getattr(v, k) + d * f)
                   for k, d in RESP_DELTA.items()}
            if upd["spo2"] is not None:
                upd["spo2"] = min(upd["spo2"], 100.0)
            upd["on_oxygen"] = (v.ts - onset) >= timedelta(minutes=RESP_RAMP_MIN * 40 / 60)
            out.append(v.model_copy(update=upd))
        label_end = end
    elif scenario == "hypotension":
        before = [v.sbp for v in vitals if v.ts <= onset and v.sbp is not None]
        sbp0 = before[-1] if before else next((v.sbp for v in vitals if v.sbp is not None), 120)
        d_sbp = min(0.0, HYPO_SBP_TARGET - sbp0)
        for v in vitals:
            if v.ts < onset:
                out.append(v)
                continue
            f = _ramp_frac(v.ts, onset, HYPO_RAMP_MIN)
            out.append(v.model_copy(update={
                "sbp": None if v.sbp is None else v.sbp + d_sbp * f,
                "hr": None if v.hr is None else v.hr + HYPO_HR_DELTA * f}))
        label_end = end
    elif scenario == "tachy_spike":
        spike_end = onset + timedelta(minutes=TACHY_MIN)
        hit = False
        for v in vitals:
            if onset <= v.ts < spike_end:
                v, hit = v.model_copy(update={"hr": TACHY_HR}), True
            out.append(v)
        if not hit:
            # leituras horárias quase nunca caem nos 3 min: acrescenta uma leitura do monitor
            prev = [v for v in vitals if v.ts <= onset][-1]
            out.append(prev.model_copy(update={"ts": onset, "hr": TACHY_HR}))
            out.sort(key=lambda o: o.ts)
        label_end = spike_end
    else:
        raise ValueError(scenario)
    return out, {"type": scenario, "ts_start": onset.isoformat(), "ts_end": label_end.isoformat()}


def pick_onset(vitals: list, base_alerts: list[dict], key: str) -> datetime | None:
    """Sorteia (semente fixa por internação e cenário) o início, fora de alertas já abertos.

    Internações com menos de 12 h ficam de fora; o início cai entre 6 h após a primeira e
    6 h antes da última leitura, em um instante sem alerta aberto na série original.
    """
    a, b = vitals[0].ts + timedelta(hours=MARGIN_H), vitals[-1].ts - timedelta(hours=MARGIN_H)
    if (vitals[-1].ts - vitals[0].ts) < timedelta(hours=MIN_STAY_H) or b <= a:
        return None
    rng = random.Random(f"{SEED}-{key}")
    span = (b - a).total_seconds()
    for _ in range(50):
        t = (a + timedelta(seconds=rng.uniform(0, span))).replace(second=0, microsecond=0)
        busy = any(al["opened"] - timedelta(minutes=30) <= t
                   <= (al["closed"] or vitals[-1].ts) for al in base_alerts)
        if not busy:
            return t
    return None


def build_injections(split: str, cfg: dict, fusion_cfg: dict) -> list[dict]:
    """Casos semissintéticos de uma divisão: internação × cenário, com início sorteado.

    O sorteio evita alertas já abertos pela configuração só NEWS2 (independe da grade).
    """
    cases = []
    for pid, vitals, rx in load_split(split):
        for k, (sv, _srx) in enumerate(segments(vitals, rx)):
            if (sv[-1].ts - sv[0].ts) < timedelta(hours=MIN_STAY_H):
                continue
            base = ev.alert_details(_filter(run_stay(sv, [], None, cfg), ev.CONFIGS["NEWS2"]),
                                    fusion_cfg)
            for sc in INJECTED:
                onset = pick_onset(sv, base, f"{pid}-{k}-{sc}")
                if onset is None:
                    continue
                series, label = inject(sv, sc, onset)
                cases.append({"patient_id": pid, "stay": k, "scenario": sc, "onset": onset,
                              "vitals": series, "label": label})
    return cases


def score_injections(cases: list[dict], iforest, cfg: dict, fusion_cfg: dict) -> dict:
    """Precisão, recall e atraso no nível de alerta (configuração completa de vitais)."""
    per_sc: dict[str, dict] = {sc: {"tp": 0, "fn": 0, "delays": []} for sc in INJECTED}
    fp = 0
    for c in cases:
        evs = _filter(run_stay(c["vitals"], [], iforest, cfg), FULL_TYPES)
        opens = [a["opened"] for a in ev.alert_details(evs, fusion_cfg)]
        a = datetime.fromisoformat(c["label"]["ts_start"])
        b = datetime.fromisoformat(c["label"]["ts_end"]) + ev.TOLERANCE
        hit = [t for t in opens if a <= t <= b]
        r = per_sc[c["scenario"]]
        if hit:
            r["tp"] += 1
            r["delays"].append((hit[0] - a).total_seconds() / 60)
        else:
            r["fn"] += 1
        fp += sum(1 for t in opens if not a <= t <= b)
    tp = sum(r["tp"] for r in per_sc.values())
    fn = sum(r["fn"] for r in per_sc.values())
    delays = [d for r in per_sc.values() for d in r["delays"]]
    med = statistics.median
    return {"cases": len(cases), "tp": tp, "fn": fn, "fp_outside_label": fp,
            "recall": tp / max(tp + fn, 1), "precision": tp / max(tp + fp, 1),
            "median_delay_min": med(delays) if delays else float("nan"),
            "by_scenario": {sc: {"tp": r["tp"], "fn": r["fn"],
                                 "recall": r["tp"] / max(r["tp"] + r["fn"], 1),
                                 "median_delay_min": med(r["delays"]) if r["delays"]
                                 else float("nan")} for sc, r in per_sc.items()}}


def vitals_load(split: str, iforest, cfg: dict, fusion_cfg: dict) -> dict:
    """Alertas/paciente-dia nas séries originais, só com os detectores de vitais."""
    n, days = 0, 0.0
    for _pid, vitals, rx in load_split(split):
        for sv, _ in segments(vitals, rx):
            evs = _filter(run_stay(sv, [], iforest, cfg), FULL_TYPES)
            n += len(ev.alert_details(evs, fusion_cfg))
            days += stay_days(sv)
    return {"alerts": n, "patient_days": days, "alerts_per_patient_day": n / max(days, 1e-9)}


def with_iforest(cfg: dict, key: str, pers: int) -> dict:
    """Cópia da config com o override do IForest do MIMIC."""
    out = copy.deepcopy(cfg)
    out["vitals"]["iforest"].setdefault("per_model", {})[MODEL] = {
        "threshold_key": key, "persistence": pers}
    return out


def tune(iforest, cfg: dict, fusion_cfg: dict, split: str = "validacao") -> list[dict]:
    """Grade do IForest do MIMIC (limiar × persistência), só na validação."""
    cases = build_injections(split, cfg, fusion_cfg)
    grid = []
    for key, pers in itertools.product(("threshold", "p0_1", "p01"), (1, 2, 3)):
        c = with_iforest(cfg, key, pers)
        inj = score_injections(cases, iforest, c, fusion_cfg)
        load = vitals_load(split, iforest, c, fusion_cfg)
        grid.append({"key": key, "persistence": pers, "inj": inj, "load": load})
        print(f"{key}/{pers}: recall={inj['recall']:.2f} "
              f"alertas/dia={load['alerts_per_patient_day']:.2f}", flush=True)
    return grid


def choose(grid: list[dict]) -> dict:
    """Maior recall; empate → menos alertas/paciente-dia; empate → menor atraso."""
    return min(grid, key=lambda g: (-g["inj"]["recall"], g["load"]["alerts_per_patient_day"],
                                    g["inj"]["median_delay_min"]))


_KEY_TEXT = {"threshold": "percentil 0,5", "p0_1": "percentil 0,1", "p01": "percentil 1"}


def tuning_markdown(grid: list[dict], best: dict) -> list[str]:
    """Tabela da grade do IForest do MIMIC."""
    md = ["# Ajuste do Isolation Forest para dados reais (T37, parte `validacao` do MIMIC)", "",
          f"Modelo `{MODEL}` (treinado na `calibracao`; percentis dos scores na `validacao`). "
          "Z-score e NEWS2 com os valores de `config/thresholds.yaml` (T36). Recall: casos "
          "semissintéticos da validação; carga: alertas por paciente-dia nas séries originais, "
          "só detectores de vitais. Critério: maior recall, depois menor carga.", "",
          "| IForest limiar | Persistência | Casos | TP | FN | Recall | Atraso mediano (min) "
          "| Alertas/paciente-dia (originais) |", "|---|---|---|---|---|---|---|---|"]
    for g in grid:
        i, lo = g["inj"], g["load"]
        mark = " **(escolhida)**" if g is best else ""
        md.append(f"| {_KEY_TEXT[g['key']]}{mark} | {g['persistence']} | {i['cases']} | {i['tp']} "
                  f"| {i['fn']} | {_f(i['recall'])} | {_f(i['median_delay_min'], 0)} "
                  f"| {_f(lo['alerts_per_patient_day'])} |")
    return md + [""]


def injection_markdown(res: list[dict]) -> list[str]:
    """Seção de recall semissintético."""
    md = ["## Recall com dados semissintéticos (cenários injetados sobre o MIMIC)", "",
          "Em cada internação com 12 h ou mais, cada cenário é injetado uma vez (série "
          "separada), num instante sorteado com semente fixa entre 6 h após o início e 6 h "
          "antes do fim, fora de alertas já abertos na série original (só NEWS2). Magnitudes "
          f"iguais às do gerador sintético, somadas ao valor real: insuficiência respiratória "
          f"em {RESP_RAMP_MIN} min (SpO₂ −10, FR +13, FC +40, O₂ suplementar após 40 min); "
          f"hipotensão em {HYPO_RAMP_MIN} min (PAS até 82, FC +25); taquicardia de "
          f"{TACHY_MIN} min a {TACHY_HR:.0f} bpm (como as leituras são horárias, uma leitura "
          "extra do monitor é acrescentada no início). TP: alerta aberto em "
          "`[início, fim + 30 min]`; os demais alertas da série contam como FP, inclusive os "
          "causados por eventos reais do paciente (por isso a precisão é um limite inferior).", "",
          "| Divisão | Casos | TP | FN | Recall | Precisão (limite inferior) "
          "| Atraso mediano (min) |", "|---|---|---|---|---|---|---|"]
    for r in res:
        i = r["injection"]
        md.append(f"| {r['split']} | {i['cases']} | {i['tp']} | {i['fn']} | {_f(i['recall'])} "
                  f"| {_f(i['precision'])} | {_f(i['median_delay_min'], 0)} |")
    md += ["", "| Divisão | Cenário | TP | FN | Recall | Atraso mediano (min) |",
           "|---|---|---|---|---|---|"]
    for r in res:
        for sc, x in r["injection"]["by_scenario"].items():
            md.append(f"| {r['split']} | `{sc}` | {x['tp']} | {x['fn']} | {_f(x['recall'])} "
                      f"| {_f(x['median_delay_min'], 0)} |")
    return md + [""]


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--splits", nargs="+", default=["validacao", "reservado"])
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "resultados")
    ap.add_argument("--tune", action="store_true",
                    help="grade do IForest do MIMIC na validação (não toca o reservado)")
    a = ap.parse_args(argv)
    iforest = CachedIForest()
    if not iforest.load():
        print(f"AVISO: {MODEL} ausente; rode train_vitals_iforest.py --mimic-split calibracao")
    ifo = iforest if iforest.enabled else None
    cfg, fusion_cfg = load_yaml("thresholds"), load_yaml("fusion")
    a.out.mkdir(parents=True, exist_ok=True)
    if a.tune:
        grid = tune(ifo, cfg, fusion_cfg)
        best = choose(grid)
        md = tuning_markdown(grid, best)
        (a.out / "mimic_tuning.md").write_text("\n".join(md), encoding="utf-8")
        print("\n".join(md))
        return
    res = []
    for s in a.splits:
        r = alarm_load(s, ifo, cfg, fusion_cfg)
        r["injection"] = score_injections(build_injections(s, cfg, fusion_cfg), ifo, cfg,
                                          fusion_cfg)
        res.append(r)
    (a.out / "mimic_results.json").write_text(
        json.dumps(res, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    md = ["# Vitais com dados reais do MIMIC-IV Demo (T37)", "",
          "Gerado por `scripts/evaluate_mimic.py`. A parte `validacao` foi usada para escolher o "
          "limiar do Isolation Forest (`mimic_tuning.md`); a parte `reservado` não ajustou nada.",
          ""] + load_markdown(res) + injection_markdown(res)
    (a.out / "mimic_results.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
