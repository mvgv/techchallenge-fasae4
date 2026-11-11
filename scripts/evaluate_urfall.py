"""Calibração e avaliação da regra de queda no UR Fall (T37, passo 8).

Roda o YOLO de pose uma vez por vídeo (cache em data/datasets/urfall/people/), calibra
`video.fall` (hip_drop_min, lying_aspect_min, lying_min_s) só na parte de calibração e mede
precisão e recall de `fall_detected` na parte reservada (quedas × ADL). Também grava
data/datasets/urfall/video_annotations.csv (formato do evaluate_video.py).

Verdade de campo: quadros rotulados 0 (caindo) ou 1 (deitado) nos CSV do dataset; sequência
de queda = um evento do primeiro ao último desses quadros. Nas ADL qualquer queda é falso alarme.
Uso: python scripts/evaluate_urfall.py [--out docs/resultados]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import pickle
from pathlib import Path

from medwatch.config import get_settings, load_yaml
from medwatch.video.bed import analyze_bed
from medwatch.video.frames import iter_frames, video_info
from medwatch.video.models import PoseEstimator, main_person

ROOT = Path(__file__).resolve().parents[1]
UR = ROOT / "data" / "datasets" / "urfall"
FPS = 30.0
TOL_S = 2.0
GRID_DROP = (0.10, 0.15, 0.20, 0.25, 0.35)
GRID_ASPECT = (1.0, 1.15, 1.3, 1.6)
GRID_LYING = (0.25, 0.5, 1.0, 2.0)


def fall_intervals(seq: str) -> list[tuple[float, float]]:
    """Intervalo (s) dos quadros de queda/deitado de uma sequência `fall-NN`; vazio nas ADL."""
    if not seq.startswith("fall"):
        return []
    frames = []
    with open(UR / "labels" / "urfall-cam0-falls.csv", newline="") as fh:
        for r in csv.reader(fh):
            if r[0] == seq and int(r[2]) >= 0:
                frames.append(int(r[1]))
    return [((min(frames) - 1) / FPS, (max(frames) - 1) / FPS)] if frames else []


def extract_people(seq: str, pose_weights: str, fps: int) -> dict:
    """Pessoas por quadro (cache em pickle); `PoseEstimator` novo por vídeo, por causa do tracking."""
    cache = UR / "people_v2" / f"{seq}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    path = UR / "video" / f"{seq}.mp4"
    info = video_info(path)
    pose = PoseEstimator(pose_weights)
    people, times = [], []
    for fr in iter_frames(path, fps):
        people.append(main_person(pose(fr.image)[0]))
        times.append(fr.t)
    data = {"people": people, "times": times, "w": info["width"], "h": info["height"]}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(pickle.dumps(data))
    return data


def detect(data: dict, thr: dict, fall: dict) -> list[dict]:
    t = {**thr, "fall": {**thr["fall"], **fall}}
    res = analyze_bed(data["people"], data["times"], data["w"], data["h"], {}, t)
    return [f for f in res.findings if f["type"] == "fall_detected"]


def score(seqs: list[str], videos: dict, thr: dict, fall: dict) -> dict:
    """Por sequência: queda detectada na janela do rótulo (TP), fora dela ou nas ADL (FP)."""
    tp = fp = fn = tn = 0
    for s in seqs:
        dets = detect(videos[s], thr, fall)
        truth = fall_intervals(s)
        if truth:
            a, b = truth[0]
            hit = [d for d in dets if d["t_start"] <= b + TOL_S and d["t_end"] >= a - TOL_S]
            tp += bool(hit)
            fn += not hit
            fp += len(dets) - len(hit)
        else:
            fp += len(dets)
            tn += not dets
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "docs" / "resultados")
    a = ap.parse_args()
    s = get_settings()
    splits = load_yaml("splits")["urfall"]
    thr = load_yaml("thresholds")["video"]
    seqs = splits["calibracao"] + splits["reservado"]
    videos = {q: extract_people(q, s.yolo_pose_weights, s.video_target_fps) for q in seqs}

    ann = UR / "video_annotations.csv"
    with open(ann, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["video", "t_start", "t_end", "type", "mode", "camera"])
        for q in seqs:
            for t0, t1 in fall_intervals(q):
                w.writerow([f"video/{q}.mp4", f"{t0:.3f}", f"{t1:.3f}", "fall_detected",
                            "bed", "ur_fall"])

    grid = []
    for d, asp, ly in itertools.product(GRID_DROP, GRID_ASPECT, GRID_LYING):
        fall = {"hip_drop_min": d, "lying_aspect_min": asp, "lying_min_s": ly}
        grid.append({**fall, **score(splits["calibracao"], videos, thr, fall)})
    best = max(grid, key=lambda g: (g["f1"], g["precision"], g["hip_drop_min"],
                                    g["lying_aspect_min"], g["lying_min_s"]))
    chosen = {k: best[k] for k in ("hip_drop_min", "lying_aspect_min", "lying_min_s")}
    before = score(splits["reservado"], videos, thr, {})
    after = score(splits["reservado"], videos, thr, chosen)
    before_cal = score(splits["calibracao"], videos, thr, {})

    top = sorted(grid, key=lambda g: (-g["f1"], -g["precision"]))[:10]

    def row(g: dict) -> str:
        return (f"| {g['hip_drop_min']} | {g['lying_aspect_min']} | {g['lying_min_s']} | "
                f"{g['tp']} | {g['fp']} | {g['fn']} | {g['precision']:.2f} | {g['recall']:.2f} | "
                f"{g['f1']:.2f} |")

    head = ("| hip_drop_min | lying_aspect_min | lying_min_s | TP | FP | FN | Precisão | Recall "
            "| F1 |\n|---|---|---|---|---|---|---|---|---|")
    n_f = sum(q.startswith("fall") for q in splits["reservado"])
    md = [
        "# Detecção de queda no UR Fall (T37)", "",
        "Câmera frontal (`cam0`), pose YOLOv8n a "
        f"{s.video_target_fps} quadros/s, regra `video.fall` do `analyze_bed` sem leito "
        "(zona `ur_fall`). Verdade: quadros rotulados como caindo/deitado. Acerto: detecção que "
        f"cruza o intervalo rotulado (±{TOL_S:g} s); detecção fora dele ou numa ADL é falso alarme.",
        "", f"Calibração: quedas 01–10 e ADL 01–10 (20 vídeos). Reservado: quedas 11–30 e ADL "
        f"11–40 ({len(splits['reservado'])} vídeos, {n_f} quedas), nunca usado na escolha.", "",
        "## Calibração (10 melhores combinações por F1)", "", head, *map(row, top), "",
        f"Escolhida: `{chosen}`. Valores anteriores (T22) na calibração: precisão "
        f"{before_cal['precision']:.2f}, recall {before_cal['recall']:.2f}.", "",
        "## Reservado", "", head,
        row({**{'hip_drop_min': 'anterior', 'lying_aspect_min': '', 'lying_min_s': ''}, **before}),
        row({**chosen, **after}), "",
        f"Sem alarme nas ADL: {after['tn']} de {len(splits['reservado']) - n_f}.", ""]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "urfall_fall.md").write_text("\n".join(md), encoding="utf-8")
    (a.out / "urfall_fall.json").write_text(json.dumps(
        {"chosen": chosen, "calibracao": best, "reservado_anterior": before,
         "reservado": after, "grid": grid}, indent=1), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
