"""Lê os .anvil do Keraal e grava recs.csv (passo 4 da T40).

Uso: python -I scripts/prepare_keraal.py data/datasets/keraal/g2a [--group 2A] [--out recs.csv]

Uma linha por intervalo de erro ("Temporal error"; se faltar, "Global error") e uma por
gravação sem erro. Referência: anotador A; se A e B discordam no rótulo global, `uncertain=1`.
A coluna `split` fica vazia: a divisão por voluntário é feita depois (config/splits.yaml).
"""

from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

COLUMNS = [
    "video", "subject", "group", "exercise", "split", "evaluation", "error_type",
    "error_size", "body_part", "t_start_s", "t_end_s", "annotator", "uncertain",
]


def _attrs(el: ET.Element) -> dict[str, str]:
    return {a.get("name", ""): (a.text or "") for a in el.iter("attribute")}


def parse_anvil(path: Path) -> dict:
    """Devolve a avaliação global e a lista de erros de um .anvil (tempos em segundos)."""
    root = ET.parse(path).getroot()
    tracks: dict[str, list[ET.Element]] = {}
    for t in root.iter("track"):
        tracks[t.get("name", "")] = list(t.iter("el"))

    glob = tracks.get("Global evaluation", [])
    evaluation = _attrs(glob[0]).get("evaluation", "") if glob else ""
    els = tracks.get("Temporal error") or tracks.get("Global error") or []
    errors = []
    for el in els:
        a = _attrs(el)
        if a.get("type", "none") == "none":
            continue
        errors.append(
            {
                "error_type": a.get("type", ""),
                "error_size": a.get("Evaluation", ""),
                "body_part": a.get("bodyPart", ""),
                "t_start_s": float(el.get("start", 0)),
                "t_end_s": float(el.get("end", 0)),
            }
        )
    return {"evaluation": evaluation, "errors": errors}


def build_rows(base: Path, group: str) -> list[dict]:
    rows: list[dict] = []
    for fa in sorted((base / "annotatorA").glob("*.anvil")):
        parts = fa.stem.split("-")  # G2A-<exercício>-S<n>-<local>-<id>
        if len(parts) < 5:
            continue
        a = parse_anvil(fa)
        fb = base / "annotatorB" / fa.name
        uncertain = int(fb.exists() and parse_anvil(fb)["evaluation"] != a["evaluation"])
        common = {
            "video": f"{parts[0]}-Anon-{'-'.join(parts[1:])}.mp4",
            "subject": parts[2],
            "group": group,
            "exercise": parts[1],
            "split": "",
            "evaluation": a["evaluation"],
            "annotator": "A",
            "uncertain": uncertain,
        }
        if a["errors"]:
            rows += [{**common, **e} for e in a["errors"]]
        else:
            empty = dict.fromkeys(("error_type", "error_size", "body_part", "t_start_s", "t_end_s"), "")
            rows.append({**common, **empty})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("--group", default="2A")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    base = Path(args.base)
    out = Path(args.out) if args.out else base.parent / f"recs_{args.group}.csv"
    rows = build_rows(base, args.group)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} linhas em {out}")


if __name__ == "__main__":
    main()
