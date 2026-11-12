"""Inspeção das anotações do Keraal (passo 1 da T40): trilhas, atributos e acordo A x B por gravação.

Uso: python -I scripts/inspect_keraal.py data/datasets/keraal/g2a
"""

from __future__ import annotations

import collections
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main(root: str) -> None:
    base = Path(root)
    tracks: collections.Counter = collections.Counter()
    attrs: collections.Counter = collections.Counter()
    ev: dict[tuple[str, str], str] = {}
    for ann in "AB":
        for f in sorted((base / f"annotator{ann}").glob("*.anvil")):
            if f.name == ".anvil":
                continue
            for t in ET.parse(f).getroot().iter("track"):
                tracks[t.get("name")] += 1
                for a in t.iter("attribute"):
                    attrs[(t.get("name"), a.get("name"), a.text)] += 1
                if t.get("name") == "Global evaluation":
                    ev[(ann, f.name)] = t.find("el/attribute").text
    print(dict(tracks))
    for k, v in sorted(attrs.items(), key=str):
        print(k, v)
    names = {k for _, k in ev}
    both = [k for k in names if ("A", k) in ev and ("B", k) in ev]
    agree = sum(ev[("A", k)] == ev[("B", k)] for k in both)
    print("gravações:", len(names), "com A e B:", len(both), "acordo global:", agree)
    print("voluntários:", sorted({k.split("-")[2] for k in names}))


if __name__ == "__main__":
    main(sys.argv[1])
