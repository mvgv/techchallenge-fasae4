"""Gera (ou atualiza) as divisões de config/splits.yaml a partir dos dados baixados.

Uso: python scripts/make_splits.py --mimic | --esc50 | --urfall | --commonvoice | --rehab24
Cada opção reescreve só a sua seção; as outras ficam como estão.
"""
import argparse
import random
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "config" / "splits.yaml"
SEED = 42
HEADER = (
    "# Divisões dos datasets públicos (T37). Gerado por scripts/make_splits.py; não edite à mão.\n"
    "# 'reservado' nunca ajusta nada: serve só para o número final e para a demonstração.\n"
)


def split_ids(ids: list[str], fractions: tuple[float, ...], names: tuple[str, ...],
              seed: int = SEED) -> dict[str, list[str]]:
    """Ordena, embaralha com `seed` e corta `ids` nas frações dadas (a última leva o resto)."""
    ids = sorted(set(ids))
    random.Random(seed).shuffle(ids)
    out, start = {}, 0
    for i, (name, frac) in enumerate(zip(names, fractions, strict=True)):
        end = len(ids) if i == len(names) - 1 else start + round(frac * len(ids))
        out[name] = sorted(ids[start:end])
        start = end
    return out


def mimic_splits(vitals_parquet: Path) -> dict:
    """60/20/20 por paciente do MIMIC (calibracao, validacao, reservado)."""
    import pandas as pd
    ids = pd.read_parquet(vitals_parquet, columns=["patient_id"])["patient_id"].unique()
    return {"seed": SEED, "unit": "patient_id",
            **split_ids(list(ids), (0.6, 0.2, 0.2), ("calibracao", "validacao", "reservado"))}


def esc50_splits(meta_csv: Path) -> dict:
    """ESC-50: folds 1–3 para calibração e 4–5 reservados (os folds do próprio dataset)."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from download_datasets import ESC50_NEGATIVE, ESC50_POSITIVE, esc50_selection
    rows = esc50_selection(meta_csv)
    return {"dataset": "ESC-50", "unit": "clip (filename)", "rule": "fold 1-3 / fold 4-5",
            "positive_classes": list(ESC50_POSITIVE), "negative_classes": list(ESC50_NEGATIVE),
            "calibracao": [r["filename"] for r in rows if int(r["fold"]) <= 3],
            "reservado": [r["filename"] for r in rows if int(r["fold"]) >= 4]}


def urfall_splits() -> dict:
    """UR Fall: quedas 01–10 e ADL 01–10 para calibração; o resto reservado (regra do plano)."""
    falls = [f"fall-{i:02d}" for i in range(1, 31)]
    adls = [f"adl-{i:02d}" for i in range(1, 41)]
    return {"dataset": "UR Fall Detection (cam0)", "unit": "sequência",
            "rule": "fall 01-10 e adl 01-10 / fall 11-30 e adl 11-40",
            "calibracao": falls[:10] + adls[:10], "reservado": falls[10:] + adls[10:]}


def rehab24_splits(seg_csv: Path) -> dict:
    """REHAB24-6, agachamento (Ex6): por voluntário, 4 calibração / 2 validação / 3 reservado.

    O plano previa 10 voluntários (5/2/3), mas só 9 têm agachamento: o reservado fica com 3
    e a calibração com 4. Cada voluntário tem um único vídeo (`PM_xxx`); a unidade é o voluntário.
    """
    import csv
    people: dict[str, str] = {}
    with open(seg_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if r["exercise_id"] == "6":
                people[r["person_id"]] = r["video_id"]
    ids = sorted(people, key=int)
    parts = split_ids(ids, (4 / 9, 2 / 9, 3 / 9), ("calibracao", "validacao", "reservado"))
    return {"dataset": "REHAB24-6 (Ex6, agachamento)", "seed": SEED, "unit": "person_id",
            "rule": "4 calibração / 2 validação / 3 reservado, por voluntário (só 9 têm Ex6)",
            **parts, "videos": {k: people[k] for k in ids}}


def load_splits(path: Path = SPLITS) -> dict:
    """Lê o splits.yaml (vazio se não existir)."""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}


def save_section(name: str, section: dict, path: Path = SPLITS) -> None:
    """Grava a seção `name` mantendo as demais."""
    data = load_splits(path)
    data[name] = section
    path.write_text(HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                                            width=100), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mimic", action="store_true")
    ap.add_argument("--esc50", action="store_true")
    ap.add_argument("--urfall", action="store_true")
    ap.add_argument("--rehab24", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    a = ap.parse_args(argv)
    if a.mimic:
        sec = mimic_splits(a.data_dir / "mimic" / "vitals.parquet")
        save_section("mimic", sec)
        print({k: len(v) for k, v in sec.items() if isinstance(v, list)})
    if a.esc50:
        sec = esc50_splits(a.data_dir / "datasets" / "esc50" / "meta" / "esc50.csv")
        save_section("audio", sec)
        print({k: len(v) for k, v in sec.items() if k in ("calibracao", "reservado")})
    if a.urfall:
        sec = urfall_splits()
        save_section("urfall", sec)
        print({k: len(v) for k, v in sec.items() if k in ("calibracao", "reservado")})
    if a.rehab24:
        sec = rehab24_splits(a.data_dir / "datasets" / "rehab24" / "Segmentation.csv")
        save_section("rehab24", sec)
        print({k: v for k, v in sec.items() if k in ("calibracao", "validacao", "reservado")})


if __name__ == "__main__":
    main()
