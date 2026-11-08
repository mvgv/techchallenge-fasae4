"""Conversão de áudio para WAV 16 kHz mono PCM 16-bit via ffmpeg."""
import subprocess
from pathlib import Path


def to_wav_16k_mono(src: Path, dst: Path) -> Path:
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000",
           "-sample_fmt", "s16", str(dst)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg não encontrado no PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg falhou: {stderr}") from exc
    return dst


def duration_seconds(wav: Path) -> float:
    import soundfile as sf

    return float(sf.info(str(wav)).duration)
