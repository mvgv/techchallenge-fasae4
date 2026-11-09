"""Baixa os datasets públicos usados na T37 para data/ (nada disso vai para o Git).

Uso: python scripts/download_datasets.py --mimic [--esc50] [--urfall]
Só usa a biblioteca padrão (urllib, zipfile) e o ffmpeg; sem wget nem unzip.
"""
import argparse
import shutil
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

MIMIC_BASE = "https://physionet.org/files/mimic-iv-demo/2.2/"
MIMIC_FILES = ("icu/chartevents.csv.gz", "hosp/prescriptions.csv.gz")
UA = {"User-Agent": "medwatch-dataset-downloader/1.0"}


def fetch(url: str, dest: Path, force: bool = False) -> Path:
    """Baixa `url` para `dest` (pula se já existir), via arquivo temporário."""
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers=UA)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
                shutil.copyfileobj(resp, fh, length=1 << 20)
            break
        except OSError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    tmp.replace(dest)
    return dest


def download_mimic(out: Path) -> None:
    """Baixa chartevents e prescriptions do MIMIC-IV Demo 2.2 e gera os parquets."""
    for rel in MIMIC_FILES:
        p = fetch(MIMIC_BASE + rel, out / rel)
        print(f"ok {p} ({p.stat().st_size / 1e6:.1f} MB)")
    from prepare_mimic import prepare
    prepare(out)


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mimic", action="store_true", help="MIMIC-IV Demo (PhysioNet)")
    ap.add_argument("--esc50", action="store_true", help="ESC-50 (sons respiratórios)")
    ap.add_argument("--urfall", action="store_true", help="UR Fall Detection (cam0)")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    a = ap.parse_args(argv)
    if not (a.mimic or a.esc50 or a.urfall):
        ap.error("escolha ao menos um dataset")
    if a.mimic:
        download_mimic(a.data_dir / "mimic")
    if a.esc50:
        download_esc50(a.data_dir / "datasets" / "esc50")
    if a.urfall:
        download_urfall(a.data_dir / "datasets" / "urfall")


ESC50_BASE = "https://raw.githubusercontent.com/karolpiczak/ESC-50/master/"
ESC50_POSITIVE = ("coughing", "breathing", "snoring", "sneezing")
ESC50_NEGATIVE = ("clock_tick", "keyboard_typing", "door_wood_knock", "rain", "dog", "laughing")


def esc50_selection(meta_csv: Path) -> list[dict]:
    """Linhas do `esc50.csv` das classes usadas (positivas e negativas), em ordem."""
    import csv
    with open(meta_csv, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["category"] in ESC50_POSITIVE + ESC50_NEGATIVE]
    return sorted(rows, key=lambda r: r["filename"])


def download_esc50(out: Path) -> None:
    """Baixa o `meta/esc50.csv` e só os WAV das classes escolhidas (40 por classe)."""
    from concurrent.futures import ThreadPoolExecutor
    meta = fetch(ESC50_BASE + "meta/esc50.csv", out / "meta" / "esc50.csv")
    rows = esc50_selection(meta)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda r: fetch(ESC50_BASE + "audio/" + r["filename"],
                                      out / "audio" / r["filename"]), rows))
    size = sum((out / "audio" / r["filename"]).stat().st_size for r in rows)
    print(f"ok ESC-50: {len(rows)} clipes ({size / 1e6:.0f} MB) em {out}")


def download_urfall(out: Path) -> None:  # implementado no passo 8
    """Placeholder até o passo 8 da T37."""
    raise SystemExit("UR Fall ainda não implementado")


if __name__ == "__main__":
    main()
