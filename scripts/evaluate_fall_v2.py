"""Queda v2 (T41, parte A): diagnóstico no desenvolvimento, ajuste e medição no reservado novo.

Desenvolvimento = UR Fall inteiro (70 sequências, caches de pose de evaluate_urfall.py);
reservado novo = CAUCAFall (100 vídeos), seção `fall_v2` de config/splits.yaml.

Uso: python scripts/evaluate_fall_v2.py --diagnose   (passo A2: só desenvolvimento)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import csv  # noqa: E402
import pickle  # noqa: E402

from evaluate_urfall import TOL_S, UR, detect, extract_people, fall_intervals  # noqa: E402

from medwatch.config import get_settings, load_yaml  # noqa: E402
from medwatch.video.bed import HIP_IDX, LYING_GAP_S  # noqa: E402
from medwatch.video.models import Detection, fallback_person  # noqa: E402

OUT = ROOT / "docs" / "resultados"
CF = ROOT / "data" / "datasets" / "caucafall"
DET_MIN_CONF = 0.10   # o cache guarda pessoas a partir desta confiança; a grade escolhe o corte


def cauca_videos() -> dict[str, dict]:
    """Linhas de `videos.csv` do CAUCAFall por sequência."""
    with open(CF / "videos.csv", newline="", encoding="utf-8") as fh:
        return {r["seq"]: r for r in csv.DictReader(fh)}


def cauca_intervals(row: dict) -> list[tuple[float, float]]:
    """Intervalo (s) rotulado como queda (corpo no chão); vazio nas ADL."""
    if not row["fall_first"]:
        return []
    fps = float(row["fps"])
    return [(int(row["fall_first"]) / fps, int(row["fall_last"]) / fps)]


def video_path(seq: str) -> Path:
    """Caminho do vídeo de uma sequência do UR Fall (`fall-NN`, `adl-NN`) ou do CAUCAFall."""
    if seq.startswith(("fall-", "adl-")):
        return UR / "video" / f"{seq}.mp4"
    return CF / cauca_videos()[seq]["avi"]


def truth_of(seq: str) -> list[tuple[float, float]]:
    """Verdade de campo de uma sequência de qualquer um dos dois datasets."""
    if seq.startswith(("fall-", "adl-")):
        return fall_intervals(seq)
    return cauca_intervals(cauca_videos()[seq])


def cached_people(seq: str, pose_weights: str, fps: int) -> dict:
    """Poses por quadro: o cache do UR Fall (T37) ou um cache novo para o CAUCAFall."""
    if seq.startswith(("fall-", "adl-")):
        return extract_people(seq, pose_weights, fps)
    cache = CF / "people" / f"{seq}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    from medwatch.video.frames import iter_frames, video_info
    from medwatch.video.models import PoseEstimator, main_person

    path = video_path(seq)
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


def cached_dets(seq: str, det_weights: str, fps: int, detector=None) -> list[list[Detection]]:
    """Pessoas do detector YOLO por quadro (confiança ≥ `DET_MIN_CONF`), em cache."""
    base = UR if seq.startswith(("fall-", "adl-")) else CF
    cache = base / "det_v2" / f"{seq}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    from medwatch.video.frames import iter_frames
    from medwatch.video.models import Detector

    det = detector or Detector(det_weights)
    out = []
    for fr in iter_frames(video_path(seq), fps):
        out.append([d for d in det(fr.image, conf=DET_MIN_CONF)[0] if d.cls == "person"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(pickle.dumps(out))
    return out


def with_fallback(data: dict, dets: list[list[Detection]] | None, min_conf: float | None) -> dict:
    """Preenche os quadros sem pose com a caixa do detector (confiança ≥ `min_conf`)."""
    if not dets or min_conf is None:
        return data
    if len(dets) != len(data["people"]):
        raise ValueError("cache do detector e das poses com números de quadros diferentes")
    people = [p if p is not None else fallback_person(d, min_conf)
              for p, d in zip(data["people"], dets, strict=True)]
    return {**data, "people": people}
CAUSES = {
    "a": "nenhuma pessoa detectada pela pose no chão",
    "b": "pessoa detectada, mas sem os pontos do quadril",
    "c": "descida do quadril abaixo de `hip_drop_min`",
    "d": "caixa sem a proporção de deitado (largura/altura)",
    "e": "o vídeo termina antes de `lying_min_s`",
}


def _hip_y(p, height: float, min_conf: float) -> float | None:
    if p is None or not all(p.kp_conf[i] >= min_conf for i in HIP_IDX):
        return None
    return float(sum(p.keypoints[i][1] for i in HIP_IDX) / 2 / height)


def _aspect(p) -> float | None:
    if p is None:
        return None
    w, h = p.xyxy[2] - p.xyxy[0], p.xyxy[3] - p.xyxy[1]
    return float(w / h) if h > 0 else None


def diagnose(data: dict, truth: tuple[float, float], thr: dict) -> dict:
    """Causa de uma queda perdida: a porta mais avançada da regra atual no par mais favorável.

    Percorre os pares (i, j = primeiro quadro ≥ i + `window_s`) com j a partir do início do
    intervalo rotulado (menos a tolerância). Portas, em ordem: pessoa em j (a), quadril em i e
    j (b), descida ≥ `hip_drop_min` (c), proporção de deitado em j (d), permanência deitada
    ≥ `lying_min_s` antes do fim do vídeo (e). A causa é a porta em que o melhor par parou.
    """
    fall = thr["fall"]
    min_conf = thr.get("keypoint_min_conf", 0.5)
    people, times, h = data["people"], data["times"], data["h"]
    hy = [_hip_y(p, h, min_conf) for p in people]
    asp = [_aspect(p) for p in people]
    n = len(times)
    best = {"gate": "a", "drop": None, "aspect": None, "lying_s": None}
    order = "abcde"
    t0 = truth[0] - TOL_S
    for i in range(n):
        j = next((k for k in range(i + 1, n) if times[k] >= times[i] + fall["window_s"]), None)
        if j is None or times[j] < t0:
            continue
        cand = {"gate": "a", "drop": None, "aspect": asp[j], "lying_s": None}
        if people[j] is not None:
            cand["gate"] = "b"
            if hy[i] is not None and hy[j] is not None:
                cand["drop"] = hy[j] - hy[i]
                cand["gate"] = "c"
                if cand["drop"] >= fall["hip_drop_min"]:
                    cand["gate"] = "d"
                    if asp[j] is not None and asp[j] >= fall["lying_aspect_min"]:
                        cand["gate"] = "e"
                        end = k = j
                        while k + 1 < n:
                            k += 1
                            if asp[k] is not None and asp[k] >= fall["lying_aspect_min"]:
                                end = k
                            elif asp[k] is not None or times[k] - times[end] > LYING_GAP_S:
                                break
                        cand["lying_s"] = times[end] - times[j]
                        cand["after_lying_s"] = times[-1] - times[end]
        better = order.index(cand["gate"]) > order.index(best["gate"]) or (
            cand["gate"] == best["gate"] and (cand["drop"] or -1) > (best["drop"] or -1))
        if better:
            best = cand
    after = [k for k in range(n) if times[k] >= truth[0]]
    best["pose_after"] = sum(people[k] is not None for k in after) / len(after) if after else 0.0
    best["hip_after"] = sum(hy[k] is not None for k in after) / len(after) if after else 0.0
    return best


def run_diagnosis(videos: dict, seqs: list[str], thr: dict) -> list[dict]:
    """Linhas da tabela de diagnóstico para as quedas que a regra atual perde."""
    rows = []
    for s in seqs:
        truth = fall_intervals(s)
        if not truth:
            continue
        a, b = truth[0]
        dets = detect(videos[s], thr, {})
        if any(d["t_start"] <= b + TOL_S and d["t_end"] >= a - TOL_S for d in dets):
            continue
        rows.append({"seq": s, **diagnose(videos[s], truth[0], thr),
                     "dur_s": videos[s]["times"][-1], "truth": [a, b]})
    return rows


def diagnosis_md(rows: list[dict], n_falls: int, n_adl_fp: int, thr: dict) -> list[str]:
    """Seção Markdown do diagnóstico."""
    def f(v, fmt="{:.2f}"):
        return "—" if v is None else fmt.format(v)

    counts = {c: sum(r["gate"] == c for r in rows) for c in CAUSES}
    md = [
        "## Diagnóstico das quedas perdidas (passo A2, só desenvolvimento)", "",
        f"Regra da T37 (`hip_drop_min` {thr['fall']['hip_drop_min']}, `lying_aspect_min` "
        f"{thr['fall']['lying_aspect_min']}, `lying_min_s` {thr['fall']['lying_min_s']}) no UR "
        f"Fall inteiro: perde **{len(rows)} de {n_falls}** quedas; {n_adl_fp} falso(s) alarme(s) "
        "nas 40 ADL.", "",
        "Para cada queda perdida, a causa é a etapa da regra em que o par de quadros mais "
        "favorável parou (pessoa → quadril → descida → proporção → permanência).", "",
        "| Causa | Quedas |", "|---|---|",
        *[f"| ({c}) {CAUSES[c]} | {counts[c]} |" for c in CAUSES], "",
        "| Sequência | Causa | Descida do quadril | Largura/altura em j | Deitado pela regra (s) "
        "| Quadros com pose após o início | Com quadril | Duração (s) |",
        "|---|---|---|---|---|---|---|---|",
        *[f"| {r['seq']} | ({r['gate']}) | {f(r['drop'])} | {f(r['aspect'])} | "
          f"{f(r['lying_s'])} | {r['pose_after']:.0%} | {r['hip_after']:.0%} | "
          f"{r['dur_s']:.1f} |" for r in rows], "",
        "Leitura:", "",
        "- Nenhuma queda é perdida por falta total de pessoa: a pose acha a pessoa na descida, "
        "mas a perde depois de ela chegar ao chão (coluna \"quadros com pose\"). Isso também "
        "derruba a permanência: sem pose, a fase deitada não é confirmada (causa e).",
        "- O UR Fall tem duas posições de câmera (quadril em pé a ~57% e a ~70% da altura do "
        "quadro). Na mais distante a pessoa é pequena e uma queda real move o quadril só 3% a "
        "10% da altura do **quadro** (causa c): a descida precisa ser medida em relação à "
        "altura da **pessoa** antes da queda.",
        "- Quem cai em direção à câmera fica com a caixa alta e estreita (largura/altura de 0,4 "
        "a 1,1), mas a altura da caixa cai muito (causa d): \"deitado\" precisa aceitar também "
        "uma queda grande da altura da caixa.",
        "- Os clipes terminam até 0,5 s depois de a pessoa deitar (causa e): o fim do vídeo, ou "
        "a perda da pose com a pessoa já deitada, precisa contar como fim da fase deitada.", ""]
    return md


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--diagnose", action="store_true")
    ap.add_argument("--cache", action="store_true",
                    help="gera os caches de pose (CAUCAFall) e de detecção (os dois datasets)")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args()
    s = get_settings()
    thr = load_yaml("thresholds")["video"]
    split = load_yaml("splits")["fall_v2"]
    dev = split["desenvolvimento"]
    if a.cache:
        from medwatch.video.models import Detector

        det = Detector(s.yolo_det_weights)
        for k, q in enumerate(dev + split["reservado"]):
            d = cached_people(q, s.yolo_pose_weights, s.video_target_fps)
            dets = cached_dets(q, s.yolo_det_weights, s.video_target_fps, det)
            if len(dets) != len(d["people"]):
                raise SystemExit(f"{q}: {len(dets)} detecções x {len(d['people'])} poses")
            print(f"[{k + 1}] {q}: {len(dets)} quadros", flush=True)
        return
    videos = {q: extract_people(q, s.yolo_pose_weights, s.video_target_fps) for q in dev}
    if a.diagnose:
        rows = run_diagnosis(videos, dev, thr)
        n_f = sum(q.startswith("fall") for q in dev)
        fp = sum(len(detect(videos[q], thr, {})) for q in dev if q.startswith("adl"))
        md = diagnosis_md(rows, n_f, fp, thr)
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "fall_v2_diagnostico.json").write_text(json.dumps(rows, indent=1),
                                                        encoding="utf-8")
        (a.out / "fall_v2.md").write_text("\n".join(
            ["# Queda v2 (T41, parte A)", "", *md]), encoding="utf-8")
        print("\n".join(md))


if __name__ == "__main__":
    main()
