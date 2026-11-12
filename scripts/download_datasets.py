"""Baixa os datasets públicos usados na T37 para data/ (nada disso vai para o Git).

Uso: python scripts/download_datasets.py --mimic [--esc50] [--urfall]
Só usa a biblioteca padrão (urllib, zipfile) e o ffmpeg; sem wget nem unzip.
"""
import argparse
import shutil
import sys
import time
import urllib.error
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
    for attempt in range(4):
        # retoma de onde parou (o servidor do Keraal é lento e cai); 416 = já completo
        done = tmp.stat().st_size if tmp.exists() else 0
        headers = dict(UA, **({"Range": f"bytes={done}-"} if done else {}))
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as resp:
                mode = "ab" if done and resp.status == 206 else "wb"
                with open(tmp, mode) as fh:
                    shutil.copyfileobj(resp, fh, length=1 << 20)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 416:
                break
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
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


REHAB24_BASE = "https://zenodo.org/api/records/13305826/files/"
REHAB24_FILES = {
    "joints_names.txt": "3f04a37cce43086b1ea1fa49f1e4514f",
    "Segmentation.txt": "5f2a5b886c6f794f03e1a8f642738c86",
    "Segmentation.csv": "90b8fbd7445dd050bf27b17126c78fbe",
    "videos.zip": "ed183a245a1b171638e422f7a288e5a8",
}


def md5sum(path: Path) -> str:
    """MD5 de um arquivo, lido em blocos."""
    import hashlib
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_rehab24(out: Path) -> None:
    """Baixa os arquivos do REHAB24-6 (Zenodo, CC BY-NC 4.0) e confere os md5."""
    for name, md5 in REHAB24_FILES.items():
        p = fetch(f"{REHAB24_BASE}{name}/content", out / name)
        if md5sum(p) != md5:
            p.unlink()
            raise SystemExit(f"md5 diferente em {name}: arquivo apagado, rode de novo")
        print(f"ok {p} ({p.stat().st_size / 1e6:.1f} MB, md5 conferido)")


KERAAL_BASE = "https://keraal.enstb.org/data/"
KERAAL_FILES = ("group1A.tar.xz", "group2A.tar.xz", "readme_files_format.txt")


def download_keraal(out: Path) -> None:
    """Baixa os grupos 1A e 2A do Keraal (CC BY-NC-SA, dados clínicos) e extrai com tarfile."""
    import tarfile
    free = shutil.disk_usage(out.parent if out.parent.exists() else ROOT).free
    if free < 6 * 10**9:
        raise SystemExit("espaço insuficiente em disco para o Keraal (precisa de ~6 GB)")
    for name in KERAAL_FILES:
        p = fetch(KERAAL_BASE + name, out / name)
        print(f"ok {p} ({p.stat().st_size / 1e6:.1f} MB)")
        if name.endswith(".tar.xz"):
            dest = out / name.removesuffix(".tar.xz")
            if not dest.exists():
                dest.mkdir(parents=True)
                with tarfile.open(p, "r:xz") as tf:
                    tf.extractall(dest, filter="data")


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mimic", action="store_true", help="MIMIC-IV Demo (PhysioNet)")
    ap.add_argument("--esc50", action="store_true", help="ESC-50 (sons respiratórios)")
    ap.add_argument("--urfall", action="store_true", help="UR Fall Detection (cam0)")
    ap.add_argument("--rehab24", action="store_true", help="REHAB24-6 (fisioterapia, Zenodo)")
    ap.add_argument("--keraal", action="store_true", help="Keraal (fisioterapia, grupos 1A e 2A)")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    a = ap.parse_args(argv)
    if not (a.mimic or a.esc50 or a.urfall or a.rehab24 or a.keraal):
        ap.error("escolha ao menos um dataset")
    if a.mimic:
        download_mimic(a.data_dir / "mimic")
    if a.esc50:
        download_esc50(a.data_dir / "datasets" / "esc50")
    if a.urfall:
        download_urfall(a.data_dir / "datasets" / "urfall")
    if a.rehab24:
        download_rehab24(a.data_dir / "datasets" / "rehab24")
    if a.keraal:
        download_keraal(a.data_dir / "datasets" / "keraal")


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


URFALL_BASE = "https://fenix.ur.edu.pl/~mkepski/ds/data/"
URFALL_FALLS = tuple(f"fall-{i:02d}" for i in range(1, 31))
URFALL_ADLS = tuple(f"adl-{i:02d}" for i in range(1, 41))
URFALL_FPS = 30


def urfall_rgb_mp4(src: Path, dest: Path) -> Path:
    """Recorta a metade RGB (direita) do MP4 do site e grava H.264 640×480 30 fps."""
    import subprocess
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".part.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
                    "-vf", "crop=iw/2:ih:iw/2:0,scale=640:480", "-r", str(URFALL_FPS),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(tmp)], check=True)
    tmp.replace(dest)
    return dest


def download_urfall(out: Path) -> None:
    """Baixa os MP4 da câmera frontal (cam0) e os rótulos por quadro; gera os MP4 só RGB.

    O site oferece cada sequência como ZIP de PNG (~50 MB) e como MP4 com profundidade e RGB
    lado a lado (1–3 MB); usamos o MP4 e recortamos a metade RGB.
    """
    from concurrent.futures import ThreadPoolExecutor
    for f in ("urfall-cam0-falls.csv", "urfall-cam0-adls.csv"):
        fetch(URFALL_BASE + f, out / "labels" / f)
    seqs = URFALL_FALLS + URFALL_ADLS

    def one(seq: str) -> Path:
        raw = fetch(URFALL_BASE + f"{seq}-cam0.mp4", out / "raw" / f"{seq}-cam0.mp4")
        fetch(URFALL_BASE + f"{seq}-data.csv", out / "raw" / f"{seq}-data.csv")
        return urfall_rgb_mp4(raw, out / "video" / f"{seq}.mp4")

    with ThreadPoolExecutor(max_workers=4) as pool:
        done = list(pool.map(one, seqs))
    size = sum(p.stat().st_size for p in done)
    print(f"ok UR Fall: {len(done)} vídeos RGB ({size / 1e6:.0f} MB) em {out / 'video'}")


if __name__ == "__main__":
    main()
