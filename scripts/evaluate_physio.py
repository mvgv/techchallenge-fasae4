"""Avaliação da análise de fisioterapia com o REHAB24-6, agachamento (T39, passos 4 a 7).

Etapas (cada uma só usa as partes permitidas de `config/splits.yaml`, seção `rehab24`):
  camera  escolhe a câmera pela contagem de repetições na calibração;
  tune    monta a referência (repetições corretas da calibração) e busca limiares na validação;
  final   mede no reservado com a referência e os limiares já escolhidos.
Pré-requisitos: prepare_rehab24.py e cache_rehab24_poses.py. Saídas em docs/resultados/.

Cada vídeo tem blocos de ~10 repetições com a mesma orientação do voluntário. A análise roda
por bloco (de 1 s antes da primeira repetição a 1 s depois da última), como num clipe curto.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_exercise_reference import reference_from_intervals  # noqa: E402
from make_splits import load_splits  # noqa: E402

from medwatch.video.geometry import angle_series  # noqa: E402
from medwatch.video.models import Person  # noqa: E402
from medwatch.video.physio import analyze_physio  # noqa: E402
from medwatch.video.reps import segment_reps  # noqa: E402

BASE = ROOT / "data" / "datasets" / "rehab24"
OUT = ROOT / "docs" / "resultados"
FPS = 10.0
PAD_S = 1.0
MIN_CONF = 0.5
FINDING_PREFIX = "physio_"
GRID = {
    "rom_min_ratio": [0.6, 0.7, 0.8, 0.9],
    "asymmetry_max_deg": [10, 15, 20, 30],
    "dtw_max": [10, 15, 20, 25],
    "trunk_max_deg": [20, 30, 40, 50],
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


def load_reps(path: Path = BASE / "reps.csv") -> list[dict]:
    """Linhas de reps.csv com os tempos como float."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["camera"] = int(r["camera"])
        r["subject"] = int(r["subject"])
        r["rep_start_s"] = float(r["rep_start_s"])
        r["rep_end_s"] = float(r["rep_end_s"])
    return rows


def load_poses(video: str) -> tuple[np.ndarray, list[Person | None]]:
    """Tempos e pessoas (None sem detecção) do cache de poses de um vídeo."""
    d = np.load(BASE / "poses" / (Path(video).stem + ".npz"))
    people = [None if np.isnan(kp).any() else Person(None, (0, 0, 1, 1), kp, c)
              for kp, c in zip(d["kp"], d["conf"], strict=True)]
    return d["t"], people


def blocks_of(rows: list[dict], camera: int, splits: set[str]) -> list[dict]:
    """Blocos (vídeo, orientação) de repetições consecutivas, com a janela de análise."""
    sel = [r for r in rows if r["camera"] == camera and r["split"] in splits]
    out = []
    for video in dict.fromkeys(r["video"] for r in sel):
        reps = [r for r in sel if r["video"] == video]
        for ori, g in itertools.groupby(reps, key=lambda r: r["orientation"]):
            g = list(g)
            out.append({"video": video, "subject": g[0]["subject"], "split": g[0]["split"],
                        "orientation": ori, "reps": g,
                        "t0": g[0]["rep_start_s"] - PAD_S, "t1": g[-1]["rep_end_s"] + PAD_S})
    return out


def window(block: dict, t: np.ndarray, people: list) -> tuple[np.ndarray, list]:
    """Tempos e pessoas dentro da janela do bloco."""
    idx = np.where((t >= block["t0"]) & (t <= block["t1"]))[0]
    return t[idx], [people[i] for i in idx]


def count_reps(block: dict, t: np.ndarray, people: list, cfg: dict) -> int:
    """Repetições detectadas pela segmentação (sem achados) no bloco."""
    _, pp = window(block, t, people)
    s = angle_series(pp, cfg["joints"], MIN_CONF)[cfg["primary_joint"]]
    return len(segment_reps(s, FPS, cfg["rep_min_prominence_deg"], cfg["rep_min_distance_s"]))


def choose_camera(rows: list[dict], cfg: dict) -> dict:
    """Erro absoluto médio de contagem por câmera, só na calibração."""
    res = {}
    for cam in (17, 18):
        errs, per_ori = [], {}
        for b in blocks_of(rows, cam, {"calibracao"}):
            t, people = load_poses(b["video"])
            e = abs(count_reps(b, t, people, cfg) - len(b["reps"]))
            errs.append(e)
            per_ori.setdefault(b["orientation"], []).append(e)
        res[cam] = {"mae": float(np.mean(errs)), "blocks": len(errs),
                    "mae_by_orientation": {k: float(np.mean(v)) for k, v in per_ori.items()}}
    res["chosen"] = min((17, 18), key=lambda c: res[c]["mae"])
    return res


def build_reference(rows: list[dict], camera: int, cfg: dict) -> dict:
    """Referência com as repetições corretas anotadas da calibração (câmera escolhida)."""
    series_list, intervals = [], []
    for video in dict.fromkeys(r["video"] for r in rows
                               if r["camera"] == camera and r["split"] == "calibracao"):
        t, people = load_poses(video)
        series = angle_series(people, cfg["joints"], MIN_CONF)
        ivs = []
        for r in rows:
            if r["video"] == video and r["label"] == "correct":
                a = int(np.searchsorted(t, r["rep_start_s"]))
                b = int(np.searchsorted(t, r["rep_end_s"]))
                if b - a >= 5:
                    ivs.append((a, min(b, len(t) - 1)))
        series_list.append(series)
        intervals.append(ivs)
    return reference_from_intervals("squat", series_list, intervals, FPS)


def covered_reps(findings: list[dict]) -> set[int]:
    """Números das repetições (da detecção) cobertos por algum achado `physio_*`."""
    out: set[int] = set()
    for f in findings:
        if not f["type"].startswith(FINDING_PREFIX):
            continue
        if f.get("rep") is not None:
            out.add(int(f["rep"]))
        out.update(int(x) for x in f.get("payload", {}).get("reps", []))
    return out


def evaluate_blocks(blocks: list[dict], cfg: dict, reference: dict | None) -> list[dict]:
    """Roda analyze_physio por bloco e liga cada repetição anotada à detectada (ponto médio)."""
    rows = []
    cache: dict[str, tuple] = {}
    for b in blocks:
        t, people = cache.setdefault(b["video"], load_poses(b["video"]))
        tw, pp = window(b, t, people)
        res = analyze_physio(pp, list(tw), FPS, cfg, reference, {"keypoint_min_conf": MIN_CONF})
        flagged = covered_reps(res.findings)
        kinds: dict[int, list[str]] = {}
        for f in res.findings:
            for n in ([f["rep"]] if f.get("rep") is not None else f["payload"].get("reps", [])):
                kinds.setdefault(int(n), []).append(f["type"])
        for r in b["reps"]:
            mid = None
            hit = [d for d in res.reps if r["rep_start_s"] <= (d["t_start"] + d["t_end"]) / 2
                   <= r["rep_end_s"]]
            if hit:
                mid = hit[0]["rep"]
            rows.append({"video": b["video"], "subject": b["subject"], "split": b["split"],
                         "orientation": b["orientation"], "label": r["label"],
                         "detected": mid is not None,
                         "flagged": mid in flagged if mid is not None else False,
                         "types": sorted(set(kinds.get(mid, []))) if mid is not None else [],
                         "n_annot": len(b["reps"]), "n_detected": len(res.reps),
                         "rep_key": (b["video"], b["orientation"])})
    return rows


def metrics(rows: list[dict]) -> dict:
    """Precisão e recall de repetição incorreta, falsos alarmes e contagem."""
    inc = [r for r in rows if r["label"] == "incorrect"]
    cor = [r for r in rows if r["label"] == "correct"]
    tp = sum(r["flagged"] for r in inc)
    fp = sum(r["flagged"] for r in cor)
    flagged = tp + fp
    prec = tp / flagged if flagged else 0.0
    rec = tp / len(inc) if inc else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "n_incorrect": len(inc), "n_correct": len(cor),
            "precision": prec, "recall": rec, "f1": f1,
            "precision_ci": wilson(tp, flagged), "recall_ci": wilson(tp, len(inc)),
            "false_alarm_rate": fp / len(cor) if cor else 0.0}


def count_errors(rows: list[dict]) -> dict:
    """Contagem anotada × detectada por bloco e erro absoluto médio."""
    per = {}
    for r in rows:
        per[r["rep_key"]] = (r["n_annot"], r["n_detected"], r["subject"], r["orientation"])
    errs = [abs(a - d) for a, d, _, _ in per.values()]
    return {"blocks": [{"video": k[0], "subject": s, "orientation": o, "annotated": a,
                        "detected": d} for k, (a, d, s, o) in per.items()],
            "mae": float(np.mean(errs)) if errs else 0.0}


def tune(rows: list[dict], camera: int, cfg: dict, reference: dict) -> list[dict]:
    """Grade de limiares, medida na validação (a calibração entra como segunda opinião)."""
    out = []
    keys = list(GRID)
    for combo in itertools.product(*GRID.values()):
        c = {**cfg, **dict(zip(keys, combo, strict=True))}
        res = {"params": dict(zip(keys, combo, strict=True))}
        for split in ("validacao", "calibracao"):
            m = metrics(evaluate_blocks(blocks_of(rows, camera, {split}), c, reference))
            res[split] = m
        out.append(res)
    return out


def pooled(g: dict) -> dict:
    """Métricas de calibração e validação somadas (só 6 voluntários: separadas, são ruidosas)."""
    a, b = g["calibracao"], g["validacao"]
    tp, fp = a["tp"] + b["tp"], a["fp"] + b["fp"]
    n_inc, n_cor = a["n_incorrect"] + b["n_incorrect"], a["n_correct"] + b["n_correct"]
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / n_inc
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"tp": tp, "fp": fp, "n_incorrect": n_inc, "n_correct": n_cor, "precision": prec,
            "recall": rec, "f1": f1, "false_alarm_rate": fp / n_cor}


def pick_best(grid: list[dict]) -> dict:
    """Melhor F1 com calibração e validação somadas; desempate pelo menor falso alarme."""
    for g in grid:
        g["pooled"] = pooled(g)
    return max(grid, key=lambda g: (round(g["pooled"]["f1"], 4), -g["pooled"]["false_alarm_rate"]))


def pct(x: float) -> str:
    """Porcentagem com uma casa e vírgula decimal."""
    return f"{100 * x:.1f}%".replace(".", ",")


def ci(c: tuple[float, float]) -> str:
    """Intervalo como texto em português."""
    return f"{100 * c[0]:.0f}% a {100 * c[1]:.0f}%"


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("stage", choices=["camera", "tune", "final"])
    a = ap.parse_args(argv)
    cfg_all = yaml.safe_load((ROOT / "config" / "exercises.yaml").read_text(encoding="utf-8"))
    cfg = cfg_all["squat"]
    rows = load_reps()
    state_path = OUT / "physio_rehab24.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    assert set(load_splits()["rehab24"]["reservado"]) == {
        str(r["subject"]) for r in rows if r["split"] == "reservado"}
    if a.stage == "camera":
        state["camera"] = choose_camera(rows, cfg)
        print(json.dumps(state["camera"], indent=1))
    else:
        cam = state["camera"]["chosen"]
        if a.stage == "tune":
            ref = build_reference(rows, cam, cfg)
            (ROOT / "data" / "references").mkdir(parents=True, exist_ok=True)
            (ROOT / "data" / "references" / "squat.json").write_text(
                json.dumps(ref, indent=2), encoding="utf-8")
            grid = tune(rows, cam, cfg, ref)
            state["grid"] = grid
            best = pick_best(grid)
            p = best["pooled"]
            base_rate = p["n_incorrect"] / (p["n_incorrect"] + p["n_correct"])
            lower = wilson(p["tp"], p["tp"] + p["fp"])[0]
            state["separates"] = bool(lower > base_rate)
            state["base_rate_incorrect"] = base_rate
            if not state["separates"]:
                # nada separa as classes: mantém os valores atuais de exercises.yaml
                keys = list(GRID)
                cur = {k: cfg[k] for k in keys}
                best = next((g for g in grid if g["params"] == cur), best)
                best = {**best, "params": cur}
            state["best"] = best
            state["reference"] = {"n_reps": ref["n_reps"], "rom": ref["rom"]}
            print(json.dumps(state["best"], indent=1, default=str))
        else:
            ref = json.loads((ROOT / "data" / "references" / "squat.json").read_text())
            best = state["best"]["params"]
            final = {**cfg, **best}
            r = evaluate_blocks(blocks_of(rows, cam, {"reservado"}), final, ref)
            state["final"] = {"params": best, "metrics": metrics(r), "counts": count_errors(r),
                              "rows": r}
            print(json.dumps({k: v for k, v in state["final"].items() if k != "rows"},
                             indent=1, default=str))
    OUT.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
