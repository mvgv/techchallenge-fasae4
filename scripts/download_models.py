"""Baixa os modelos usados pelos workers (idempotente)."""
import shutil
import sys
from pathlib import Path

from medwatch.config import get_settings

YOLO_WEIGHTS = ["yolov8n.pt", "yolov8n-pose.pt"]
AST_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"


def download_yolo(models_dir: Path) -> None:
    from ultralytics import YOLO

    for name in YOLO_WEIGHTS:
        dest = models_dir / name
        if dest.exists():
            print(f"[ok] {dest}")
            continue
        model = YOLO(name)  # baixa para o diretório atual se não existir
        src = Path(getattr(model, "ckpt_path", None) or name)
        shutil.copy2(src, dest)
        if src.resolve() != dest.resolve() and src.parent.resolve() == Path.cwd().resolve():
            src.unlink(missing_ok=True)
        print(f"[baixado] {dest}")


def download_ast() -> None:
    from transformers import ASTForAudioClassification, AutoFeatureExtractor

    AutoFeatureExtractor.from_pretrained(AST_MODEL)
    ASTForAudioClassification.from_pretrained(AST_MODEL)
    print(f"[ok] {AST_MODEL} no cache do Hugging Face")


def main() -> int:
    settings = get_settings()
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    try:
        download_yolo(settings.models_dir)
        if not settings.audio_disable_events:
            download_ast()
    except Exception as exc:  # falha de rede, por exemplo
        print(f"[erro] download de modelos falhou: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
