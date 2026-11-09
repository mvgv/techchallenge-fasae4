"""Avaliação do pipeline de vídeo contra anotações manuais.

CSV (preenchido pelo grupo): colunas `video, t_start, t_end, type`; opcionais `mode`
(physio|bed|surgery, padrão physio), `exercise` (padrão squat) e `camera`.
Uma detecção acerta se o tipo coincide e seu intervalo, ampliado em ±2 s, cruza o da anotação.
Uso: python scripts/evaluate_video.py --annotations data/samples/video_annotations.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

TOL_S = 2.0
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


class _NullDb:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _NullBus:
    def publish(self, *_a, **_k):
        pass


def load_annotations(path: Path) -> dict[str, list[dict]]:
    by_video: dict[str, list[dict]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            row["t_start"], row["t_end"] = float(row["t_start"]), float(row["t_end"])
            by_video[row["video"]].append(row)
    return by_video


def match(truth: list[dict], dets: list[dict]) -> dict[str, dict[str, int]]:
    """Contagem de tp/fp/fn por tipo, com tolerância de ±2 s."""
    res: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    used: set[int] = set()
    for t in truth:
        hit = next((i for i, d in enumerate(dets)
                    if i not in used and d["type"] == t["type"]
                    and d["t_start"] <= t["t_end"] + TOL_S and d["t_end"] >= t["t_start"] - TOL_S),
                   None)
        if hit is None:
            res[t["type"]]["fn"] += 1
        else:
            used.add(hit)
            res[t["type"]]["tp"] += 1
    for i, d in enumerate(dets):
        if i not in used:
            res[d["type"]]["fp"] += 1
    return res


def run_video(worker, path: Path, row: dict) -> list[dict]:
    from medwatch.contracts import MediaJob

    job = MediaJob(media_id=uuid4(), patient_id="EVAL", kind="video",
                   storage_uri=str(path), recorded_at=EPOCH, mode=row.get("mode") or "physio",
                   exercise=(row.get("exercise") or "squat"), camera=row.get("camera") or None)
    out = []
    for e in worker.process(job):
        a = (e.ts_start - EPOCH).total_seconds()
        end = getattr(e, "ts_end", None)
        out.append({"type": e.type, "t_start": a,
                    "t_end": (end - EPOCH).total_seconds() if end else a})
    return out


def build_worker(root: Path):
    from medwatch.storage import LocalStorage
    from medwatch.video.worker import VideoWorker

    return VideoWorker(_NullBus(), LocalStorage(root), db_module=_NullDb())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--annotations", required=True)
    ap.add_argument("--videos-dir", default=None, help="padrão: pasta do CSV")
    ap.add_argument("--out", default="docs/resultados/video_metrics.md")
    args = ap.parse_args()
    ann = Path(args.annotations)
    if not ann.exists():
        print(f"Anotações não encontradas: {ann} (passo [HUMANO]: ver data/samples/README.md)",
              file=sys.stderr)
        return 1
    vdir = Path(args.videos_dir) if args.videos_dir else ann.parent
    by_video = load_annotations(ann)

    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    with tempfile.TemporaryDirectory() as tmp:
        worker = build_worker(Path(tmp))
        for video, rows in by_video.items():
            path = vdir / video
            if not path.exists():
                print(f"Vídeo ausente, ignorado: {path}", file=sys.stderr)
                continue
            for typ, c in match(rows, run_video(worker, path, rows[0])).items():
                for k, v in c.items():
                    totals[typ][k] += v

    lines = ["# Avaliação do pipeline de vídeo", "",
             f"Tolerância temporal: ±{TOL_S:g} s.", "",
             "| Tipo | TP | FP | FN | Precisão | Recall |", "|---|---|---|---|---|---|"]
    for typ, c in sorted(totals.items()):
        p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
        r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
        lines.append(f"| {typ} | {c['tp']} | {c['fp']} | {c['fn']} | {p:.2f} | {r:.2f} |")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
