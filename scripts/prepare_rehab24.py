"""Prepara o agachamento (Ex6) do REHAB24-6: extrai os vídeos e grava reps.csv (T39, passo 3).

Uso: python scripts/prepare_rehab24.py [--data-dir data]
`reps.csv`: video, camera, subject, split, rep_start_s, rep_end_s, label, orientation.
Uma linha por repetição e por câmera (17 e 18); `label` é `correct` ou `incorrect`
(rótulo do fisioterapeuta). Os quadros da segmentação são a 30 fps.
"""
import argparse
import csv
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

FPS = 30.0
CAMERAS = {17: "{vid}-Camera17-30fps.mp4", 18: "{vid}-Camera18-30fps-transposed.mp4"}
FIELDS = ["video", "camera", "subject", "split", "rep_start_s", "rep_end_s", "label", "orientation"]


def split_of(person_id: str, splits: dict) -> str:
    """Parte (calibracao, validacao, reservado) do voluntário."""
    for name in ("calibracao", "validacao", "reservado"):
        if str(person_id) in {str(p) for p in splits[name]}:
            return name
    raise KeyError(f"voluntário {person_id} fora da divisão")


def build_rows(seg_csv: Path, splits: dict, exercise_id: str = "6") -> list[dict]:
    """Uma linha por repetição e câmera do exercício, ligada ao vídeo, ao intervalo e ao rótulo."""
    rows = []
    with open(seg_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            if r["exercise_id"] != exercise_id:
                continue
            for cam, pattern in CAMERAS.items():
                rows.append({
                    "video": pattern.format(vid=r["video_id"]),
                    "camera": cam,
                    "subject": int(r["person_id"]),
                    "split": split_of(r["person_id"], splits),
                    "rep_start_s": round(int(r["first_frame"]) / FPS, 3),
                    "rep_end_s": round(int(r["last_frame"]) / FPS, 3),
                    "label": "correct" if r["correctness"] == "1" else "incorrect",
                    "orientation": r["cam17_orientation"],
                })
    return rows


def extract_videos(zip_path: Path, out: Path, exercise_dir: str = "Ex6/") -> list[Path]:
    """Extrai só os vídeos do exercício (pula os que já existem)."""
    out.mkdir(parents=True, exist_ok=True)
    done = []
    with zipfile.ZipFile(zip_path) as z:
        for info in z.infolist():
            if not info.filename.startswith(exercise_dir) or info.is_dir():
                continue
            dest = out / Path(info.filename).name
            if not (dest.exists() and dest.stat().st_size == info.file_size):
                with z.open(info) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
            done.append(dest)
    return done


def main(argv: list[str] | None = None) -> None:
    """Ponto de entrada da linha de comando."""
    from make_splits import load_splits
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    a = ap.parse_args(argv)
    base = a.data_dir / "datasets" / "rehab24"
    videos = extract_videos(base / "videos.zip", base / "squat")
    rows = build_rows(base / "Segmentation.csv", load_splits()["rehab24"])
    with open(base / "reps.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(videos)} vídeos em {base / 'squat'}; {len(rows)} linhas em reps.csv")


if __name__ == "__main__":
    main()
