"""Concordância dos anotadores A e B do Keraal (passo 2 da T40).

Uso: python -I scripts/keraal_agreement.py data/datasets/keraal/g1a data/datasets/keraal/g2a
Por gravação: rótulo global (4 classes), correto×incorreto (Incompleto/Imóvel fora) e tipo de erro.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare_keraal import parse_anvil  # noqa: E402


def kappa(pairs: list[tuple[str, str]]) -> tuple[float, float]:
    """(proporção de acordo, kappa de Cohen)."""
    n = len(pairs)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(a == b for a, b in pairs) / n
    ca = collections.Counter(a for a, _ in pairs)
    cb = collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return po, (1.0 if pe == 1 else (po - pe) / (1 - pe))


def collect(base: Path) -> dict[str, tuple[dict, dict]]:
    out = {}
    for fa in sorted((base / "annotatorA").glob("*.anvil")):
        fb = base / "annotatorB" / fa.name
        if fa.name != ".anvil" and fb.exists():
            out[fa.stem] = (parse_anvil(fa), parse_anvil(fb))
    return out


def etype(r: dict) -> str:
    return "+".join(sorted({e["error_type"] for e in r["errors"]})) or "none"


def main(roots: list[str]) -> None:
    for root in roots:
        recs = collect(Path(root))
        glob = [(a["evaluation"], b["evaluation"]) for a, b in recs.values()]
        binary = [
            (a["evaluation"], b["evaluation"])
            for a, b in recs.values()
            if {a["evaluation"], b["evaluation"]} <= {"Correct", "Incorrect"}
        ]
        err = [
            (etype(a), etype(b))
            for a, b in recs.values()
            if a["evaluation"] == b["evaluation"] == "Incorrect"
        ]
        print(root, "gravações com A e B:", len(recs))
        for nome, p in (
            ("global (4 classes)", glob),
            ("correto×incorreto", binary),
            ("tipo de erro (ambos incorretos)", err),
        ):
            po, k = kappa(p)
            print(f"  {nome}: n={len(p)} acordo={po:.3f} kappa={k:.3f}")


if __name__ == "__main__":
    main(sys.argv[1:])
