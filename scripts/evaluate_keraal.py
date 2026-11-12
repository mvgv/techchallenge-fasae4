"""Avaliação da fisioterapia no Keraal (T40, passos 6 e 7): correto×incorreto e erro nomeado.

Uso: python -I scripts/evaluate_keraal.py [--stage tune|final|all]
Lê data/datasets/keraal/recs_*.csv e poses/ (scripts/cache_keraal_poses.py), config/splits.yaml
(seção keraal) e config/exercises.yaml. Unidade: a gravação. Referência: anotador A; gravações com
A e B discordando (`uncertain`) saem do cálculo principal. O reservado NÃO ajusta nada: a grade usa
só calibração e validação, somadas. Grava docs/resultados/physio_keraal.{md,json}.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_exercise_reference import reference_from_intervals  # noqa: E402
from make_splits import load_splits  # noqa: E402

from medwatch.video.geometry import angle_series  # noqa: E402
from medwatch.video.models import Person  # noqa: E402
from medwatch.video.physio import analyze_physio  # noqa: E402
from medwatch.video.reps import segment_reps  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "datasets" / "keraal"
OUT = ROOT / "docs" / "resultados"
MIN_CONF = 0.5
TOL_S = 2.0
EXERCISES = {"RTK": "trunk_rotation", "ELK": "lateral_stretch", "CTK": "hide_face"}
GRID = {
    "rom_min_ratio": [0.6, 0.75, 0.9],
    "asymmetry_max_deg": [15, 25, 40],
    "dtw_max": [15, 25, 40],
    "trunk_max_deg": [10, 20, 30],
}


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de Wilson de 95% para k de n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (float(max(0.0, c - h)), float(min(1.0, c + h)))


def load_recordings(base: Path = BASE) -> list[dict]:
    """Uma entrada por vídeo, com a lista de erros anotados (recs_*.csv) e a divisão."""
    sp = load_splits()["keraal"]
    where = {s: k for k in ("calibracao", "validacao", "reservado") for s in sp[k]}
    recs: dict[str, dict] = {}
    for path in sorted(base.glob("recs_*.csv")):
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                rec = recs.setdefault(r["video"], {
                    "video": r["video"], "subject": r["subject"], "group": r["group"],
                    "exercise": r["exercise"], "evaluation": r["evaluation"],
                    "uncertain": int(r["uncertain"]), "split": where.get(r["subject"], ""),
                    "errors": []})
                if r["error_type"]:
                    rec["errors"].append({
                        "type": r["error_type"], "body_part": r["body_part"],
                        "t0": float(r["t_start_s"]), "t1": float(r["t_end_s"])})
    return list(recs.values())


def load_poses(video: str) -> tuple[np.ndarray, list[Person | None], float]:
    """Tempos, pessoas (None sem detecção) e fps efetivo do cache de poses."""
    d = np.load(BASE / "poses" / (Path(video).stem + ".npz"))
    t = d["t"]
    people = [None if np.isnan(kp).any() else Person(None, (0, 0, 1, 1), kp, c)
              for kp, c in zip(d["kp"], d["conf"], strict=True)]
    fps = float(1.0 / np.median(np.diff(t))) if len(t) > 2 else 10.0
    return t, people, fps


def build_reference(recs: list[dict], exercise: str, cfg: dict) -> dict:
    """Referência com as gravações corretas (e certas) da calibração, repetições detectadas."""
    series_list, intervals, fps_all = [], [], []
    for r in recs:
        if (r["exercise"], r["split"], r["evaluation"], r["uncertain"]) != (
                exercise, "calibracao", "Correct", 0):
            continue
        _, people, fps = load_poses(r["video"])
        s = angle_series(people, cfg["joints"], MIN_CONF)
        reps = segment_reps(s[cfg["primary_joint"]], fps, cfg["rep_min_prominence_deg"],
                            cfg["rep_min_distance_s"])
        if reps:
            series_list.append(s)
            intervals.append(reps)
            fps_all.append(fps)
    return reference_from_intervals(
        exercise, series_list, intervals, float(np.mean(fps_all)) if fps_all else 10.0)


def analyze(rec: dict, cfg: dict, reference: dict | None, cache: dict) -> list[dict]:
    """Achados `physio_*` da gravação inteira."""
    if rec["video"] not in cache:
        cache[rec["video"]] = load_poses(rec["video"])
    t, people, fps = cache[rec["video"]]
    res = analyze_physio(people, [float(x) for x in t], fps, cfg, reference,
                         {"keypoint_min_conf": MIN_CONF})
    return res.findings


def overlaps(f: dict, err: dict, tol: float = TOL_S) -> bool:
    """O achado coincide no tempo com o intervalo do erro (tolerância de ±tol s)?"""
    return f["t_start"] <= err["t1"] + tol and f["t_end"] >= err["t0"] - tol


def judge(rec: dict, findings: list[dict], cfg: dict) -> dict:
    """Sinalizada ou não, e, se incorreta, se o achado nomeia o erro e coincide no tempo."""
    types = {f["type"] for f in findings}
    out = {"flagged": bool(findings), "types": sorted(types), "named": None, "timed": None,
           "not_visible": None}
    if rec["evaluation"] != "Incorrect" or not rec["errors"]:
        return out
    expected = {e["type"]: cfg.get("errors", {}).get(e["type"]) for e in rec["errors"]}
    visible = [e for e in rec["errors"] if expected[e["type"]]]
    out["not_visible"] = not visible
    if visible:
        out["named"] = any(expected[e["type"]] in types for e in visible)
        out["timed"] = any(
            f["type"] == expected[e["type"]] and overlaps(f, e)
            for e in visible for f in findings)
    return out


def prf(rows: list[dict]) -> dict:
    """Precisão, recall e falsos alarmes (correto×incorreto), com IC de Wilson."""
    inc = [r for r in rows if r["evaluation"] == "Incorrect"]
    cor = [r for r in rows if r["evaluation"] == "Correct"]
    tp = sum(r["j"]["flagged"] for r in inc)
    fp = sum(r["j"]["flagged"] for r in cor)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / len(inc) if inc else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "n_incorrect": len(inc), "n_correct": len(cor),
            "precision": prec, "recall": rec, "f1": f1,
            "precision_ci": wilson(tp, tp + fp), "recall_ci": wilson(tp, len(inc)),
            "false_alarm": fp / len(cor) if cor else 0.0,
            "false_alarm_ci": wilson(fp, len(cor))}


def run_split(recs: list[dict], exercise: str, splits: set[str], cfg: dict,
              reference: dict, cache: dict, uncertain: bool = False) -> list[dict]:
    """Avalia as gravações do exercício nas divisões dadas."""
    rows = []
    for r in recs:
        if r["exercise"] != exercise or r["split"] not in splits:
            continue
        if r["uncertain"] and not uncertain:
            continue
        rows.append({**r, "j": judge(r, analyze(r, cfg, reference, cache), cfg)})
    return rows


def tune(recs: list[dict], exercise: str, cfg: dict, reference: dict, cache: dict) -> list[dict]:
    """Grade de limiares com calibração e validação somadas (melhor F1; desempate: menos FP)."""
    out = []
    keys = list(GRID)
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(keys, combo, strict=True))
        rows = run_split(recs, exercise, {"calibracao", "validacao"}, {**cfg, **params},
                         reference, cache)
        out.append({"params": params, "metrics": prf(rows)})
    return out


def pick(grid: list[dict]) -> dict:
    """Melhor combinação: F1 e, no empate, o menor falso alarme."""
    return max(grid, key=lambda g: (round(g["metrics"]["f1"], 4), -g["metrics"]["false_alarm"]))


def pct(x: float) -> str:
    """Porcentagem com vírgula decimal."""
    return f"{100 * x:.0f}%"


def ci(c: tuple[float, float]) -> str:
    """Intervalo como texto."""
    return f"{pct(c[0])} a {pct(c[1])}"


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["tune", "final", "all"], default="all")
    a = ap.parse_args(argv)
    cfgs = yaml.safe_load((ROOT / "config" / "exercises.yaml").read_text(encoding="utf-8"))
    recs = load_recordings()
    state_path = OUT / "physio_keraal.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    cache: dict = {}
    for code, name in EXERCISES.items():
        cfg = cfgs[name]
        ref = build_reference(recs, code, cfg)
        if a.stage in ("tune", "all"):
            grid = tune(recs, code, cfg, ref, cache)
            best = pick(grid)
            state.setdefault(name, {})["grid_best"] = best
            state[name]["grid_n"] = len(grid)
            state[name]["baseline_m"] = next(
                (g["metrics"] for g in grid if all(g["params"][k] == cfg[k] for k in GRID)), None)
            state[name]["flag_all"] = {
                "precision": best["metrics"]["n_incorrect"]
                / max(1, best["metrics"]["n_incorrect"] + best["metrics"]["n_correct"])}
            print(name, "melhor", best["params"], {k: round(v, 2) for k, v in best["metrics"].items()
                                                   if isinstance(v, float)}, flush=True)
        if a.stage in ("final", "all"):
            best = state[name]["grid_best"]["params"]
            final_cfg = {**cfg, **best}
            rows = run_split(recs, code, {"reservado"}, final_cfg, ref, cache)
            rows_u = run_split(recs, code, {"reservado"}, final_cfg, ref, cache, uncertain=True)
            state[name]["final_cfg"] = best
            state[name]["reservado"] = {
                "all": prf(rows_u), "main": prf(rows),
                "pacientes": prf([r for r in rows if r["group"] == "1A"]),
                "saudaveis": prf([r for r in rows if r["group"] == "2A"]),
                "other": [{"video": r["video"], "evaluation": r["evaluation"],
                           "flagged": r["j"]["flagged"]} for r in rows_u
                          if r["evaluation"] in ("Incomplete", "Motionless")],
                "errors": [{"video": r["video"], "types": [e["type"] for e in r["errors"]],
                            **{k: r["j"][k] for k in ("flagged", "named", "timed", "not_visible")}}
                           for r in rows if r["evaluation"] == "Incorrect"],
            }
        OUT.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1, ensure_ascii=False, default=float))
    print("estado gravado em", state_path)


if __name__ == "__main__":
    main()
