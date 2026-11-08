"""Leitura de frames de vídeo com redução de taxa."""
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Frame:
    """Frame de vídeo: índice original, tempo em segundos e imagem BGR."""

    index: int
    t: float
    image: np.ndarray


def iter_frames(path: Path, target_fps: int) -> Iterator[Frame]:
    """Itera os frames do vídeo, amostrando para aproximar target_fps."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir o vídeo {path}")
    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        step = max(1, round(src_fps / target_fps))
        i = 0
        while True:
            ok, img = cap.read()
            if not ok:
                break
            if i % step == 0:
                yield Frame(i, i / src_fps, img)
            i += 1
    finally:
        cap.release()


def video_info(path: Path) -> dict:
    """Retorna fps, frames, width, height e duration_s do vídeo."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Não foi possível abrir o vídeo {path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return {
            "fps": fps,
            "frames": frames,
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration_s": frames / fps,
        }
    finally:
        cap.release()
