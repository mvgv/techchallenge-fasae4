"""Avaliação do detector de sons respiratórios (AST/AudioSet) no ESC-50 (T37).

Calibra `audio_events.min_score`, `breathing_min_score` e a inclusão de "Sneeze" só nos clipes
de calibração (folds 1–3) e mede precisão e recall por classe nos reservados (folds 4–5).
As previsões do AST ficam em cache em data/datasets/esc50/ast_predictions.json.

Uso: python scripts/evaluate_audio_events.py [--out docs/resultados]
Pré-requisitos: download_datasets.py --esc50 e make_splits.py --esc50.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
from pathlib import Path

from medwatch.audio.events import RespiratoryEventDetector, breathing_rule, window_hits
from medwatch.config import load_yaml

ROOT = Path(__file__).resolve().parents[1]
ESC = ROOT / "data" / "datasets" / "esc50"
CACHE = ESC / "ast_predictions.json"
TOP_K_DETECTOR = 15            # o detector em produção usa top_k=15
TOP_K_CACHE = 30
# rótulos do AST que contam como acerto de classe para cada classe positiva do ESC-50
EXPECTED = {"coughing": {"Cough", "Throat clearing"},
            "breathing": {"Breathing", "Gasp", "Pant", "Wheeze"},
            "snoring": {"Snoring"}, "sneezing": {"Sneeze"}}
GRID_MIN = (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5)
GRID_BREATH = (0.2, 0.3, 0.4, 0.5, 0.6)
GRID_SNEEZE = (False, True)


def load_meta() -> dict[str, dict]:
    """filename → linha do esc50.csv."""
    with open(ESC / "meta" / "esc50.csv", newline="", encoding="utf-8") as fh:
        return {r["filename"]: r for r in csv.DictReader(fh)}


def predict_all(files: list[str], cache: Path = CACHE) -> dict[str, list[dict]]:
    """Top-30 do AST por clipe (inteiro: os clipes têm 5 s, menos que a janela de 10 s)."""
    preds = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [f for f in files if f not in preds]
    if todo:
        import librosa
        from transformers import pipeline
        clf = pipeline("audio-classification", model=RespiratoryEventDetector.MODEL,
                       top_k=TOP_K_CACHE)
        for n, f in enumerate(todo, 1):
            y, sr = librosa.load(ESC / "audio" / f, sr=16000)
            preds[f] = [{"label": p["label"], "score": float(p["score"])}
                        for p in clf({"raw": y.astype("float32"), "sampling_rate": sr})]
            if n % 50 == 0:
                print(f"  {n}/{len(todo)} clipes", flush=True)
                cache.write_text(json.dumps(preds))
        cache.write_text(json.dumps(preds))
    return preds


def detect_cached(preds: list[dict], cfg: dict) -> list[dict]:
    """Mesma regra do `RespiratoryEventDetector` (uma janela) sobre a previsão em cache."""
    hits = window_hits(preds[:TOP_K_DETECTOR], cfg)
    return breathing_rule([{"label": p["label"], "max_score": p["score"]} for p in hits], cfg)


def evaluate(files: list[str], meta: dict, preds: dict, cfg: dict) -> dict:
    """Métricas por clipe: binária (respiratório × não) e por classe do ESC-50."""
    pos_classes = set(EXPECTED)
    per_class: dict[str, dict] = {}
    tp = fp = fn = tn = 0
    for f in files:
        cat = meta[f]["category"]
        events = detect_cached(preds[f], cfg)
        detected = bool(events)
        labels = {e["label"] for e in events}
        c = per_class.setdefault(cat, {"n": 0, "detected": 0, "label_ok": 0,
                                       "labels": {}})
        c["n"] += 1
        c["detected"] += detected
        for lb in labels:
            c["labels"][lb] = c["labels"].get(lb, 0) + 1
        if cat in pos_classes:
            c["label_ok"] += bool(labels & EXPECTED[cat])
            tp += detected
            fn += not detected
        else:
            fp += detected
            tn += not detected
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    # precisão por classe: entre os clipes em que o rótulo esperado da classe apareceu,
    # quantos eram mesmo daquela classe
    for cat, exp in EXPECTED.items():
        if cat not in per_class:
            continue
        pred_as = sum(1 for f in files if {e["label"] for e in detect_cached(preds[f], cfg)}
                      & exp)
        per_class[cat]["class_precision"] = (per_class[cat]["label_ok"] / pred_as
                                             if pred_as else float("nan"))
    return {"n": len(files), "tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": prec,
            "recall": rec, "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "per_class": per_class}


def with_params(base: dict, min_score: float, breath: float, sneeze: bool) -> dict:
    """Cópia da config de `audio_events` com os parâmetros da grade."""
    cfg = dict(base, min_score=min_score, breathing_min_score=breath)
    labels = [lb for lb in base["labels"] if lb != "Sneeze"]
    cfg["labels"] = labels + (["Sneeze"] if sneeze else [])
    return cfg


def tune(files: list[str], meta: dict, preds: dict, base: dict) -> list[dict]:
    """Grade na calibração; ordenada por F1 (desempate: precisão)."""
    grid = []
    for m, b, s in itertools.product(GRID_MIN, GRID_BREATH, GRID_SNEEZE):
        r = evaluate(files, meta, preds, with_params(base, m, b, s))
        grid.append({"min_score": m, "breathing_min_score": b, "sneeze": s,
                     **{k: r[k] for k in ("tp", "fp", "fn", "precision", "recall", "f1")}})
    return sorted(grid, key=lambda g: (-g["f1"], -g["precision"], -g["min_score"]))


def _f(x: float) -> str:
    return "—" if x != x else f"{x:.2f}".replace(".", ",")


def markdown(grid: list[dict], best: dict, res: dict, cal: dict) -> list[str]:
    """Relatório de calibração e do reservado."""
    md = ["# Sons respiratórios no ESC-50 (T37)", "",
          "Detector: `RespiratoryEventDetector` (AST `MIT/ast-finetuned-audioset-10-10-0.4593`, "
          "top 15 rótulos, uma janela por clipe de 5 s). Um clipe é \"respiratório\" se o "
          "detector devolve qualquer evento. Calibração: folds 1–3 (240 clipes); reservado: "
          "folds 4–5 (160 clipes), nunca usado na escolha.", "",
          "## Calibração (10 melhores combinações por F1)", "",
          "| min_score | breathing_min_score | Sneeze | TP | FP | FN | Precisão | Recall | F1 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for g in grid[:10]:
        mark = " **(escolhida)**" if g is best else ""
        md.append(f"| {g['min_score']}{mark} | {g['breathing_min_score']} "
                  f"| {'sim' if g['sneeze'] else 'não'} | {g['tp']} | {g['fp']} | {g['fn']} "
                  f"| {_f(g['precision'])} | {_f(g['recall'])} | {_f(g['f1'])} |")
    md += ["", f"Valores anteriores (T17) na calibração: precisão {_f(cal['precision'])}, "
           f"recall {_f(cal['recall'])}, F1 {_f(cal['f1'])}.", "",
           "## Reservado (folds 4–5)", "",
           f"Respiratório × não respiratório: TP {res['tp']}, FP {res['fp']}, FN {res['fn']}, "
           f"TN {res['tn']}; **precisão {_f(res['precision'])}, recall {_f(res['recall'])}, "
           f"F1 {_f(res['f1'])}**.", "",
           "| Classe ESC-50 | Grupo | Clipes | Detectados como respiratório | Recall "
           "| Rótulo esperado | Precisão da classe | Rótulos do AST |",
           "|---|---|---|---|---|---|---|---|"]
    for cat, c in sorted(res["per_class"].items(), key=lambda x: (x[0] not in EXPECTED, x[0])):
        pos = cat in EXPECTED
        labels = ", ".join(f"{k} {v}" for k, v in sorted(c["labels"].items(),
                                                         key=lambda x: -x[1]))
        md.append(f"| {cat} | {'positivo' if pos else 'negativo'} | {c['n']} | {c['detected']} "
                  f"| {_f(c['detected'] / c['n']) if pos else '—'} "
                  f"| {c['label_ok'] if pos else '—'} "
                  f"| {_f(c.get('class_precision', float('nan'))) if pos else '—'} "
                  f"| {labels or '—'} |")
    md += ["", "Recall da classe: fração dos clipes detectados como respiratórios. Rótulo "
           "esperado: clipes em que apareceu o rótulo do AST correspondente (tosse: Cough ou "
           "Throat clearing; respiração: Breathing, Gasp, Pant ou Wheeze; ronco: Snoring; "
           "espirro: Sneeze). Precisão da classe: desses rótulos, a fração que veio da classe "
           "certa. Nas classes negativas, \"detectados\" são falsos alarmes.", ""]
    return md


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "resultados")
    a = ap.parse_args(argv)
    split = load_yaml("splits")["audio"]
    meta = load_meta()
    files_cal, files_res = split["calibracao"], split["reservado"]
    preds = predict_all(files_cal + files_res)
    base = load_yaml("thresholds")["audio_events"]
    grid = tune(files_cal, meta, preds, base)
    best = grid[0]
    cfg = with_params(base, best["min_score"], best["breathing_min_score"], best["sneeze"])
    cal_old = evaluate(files_cal, meta, preds, base)
    res = evaluate(files_res, meta, preds, cfg)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "audio_events.json").write_text(json.dumps(
        {"chosen": best, "grid": grid, "reservado": res}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    md = markdown(grid, best, res, cal_old)
    (a.out / "audio_events.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))
    print("escolhido:", best)


if __name__ == "__main__":
    main()
