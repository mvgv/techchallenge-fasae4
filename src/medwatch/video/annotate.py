"""Vídeo anotado: sobreposição de zonas, tempo e achados; saída H.264 para navegador."""
from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

FINDING_WINDOW_S = 1.5
RED = (0, 0, 255)
WHITE = (255, 255, 255)
ZONE_COLOR = (0, 200, 255)


def base_image(img: np.ndarray, pose_result: object = None, det_result: object = None) -> np.ndarray:
    """Começa do `plot()` da pose (Ultralytics) e desenha as caixas da detecção por cima."""
    out = img
    if pose_result is not None and hasattr(pose_result, "plot"):
        out = pose_result.plot()
    if det_result is not None and hasattr(det_result, "boxes") and det_result.boxes is not None:
        out = out.copy()
        names = getattr(det_result, "names", {})
        for b, c in zip(det_result.boxes.xyxy.cpu().numpy(),
                        det_result.boxes.cls.cpu().numpy(), strict=True):
            x0, y0, x1, y1 = map(int, b)
            cv2.rectangle(out, (x0, y0), (x1, y1), (255, 128, 0), 2)
            cv2.putText(out, str(names.get(int(c), int(c))), (x0, max(12, y0 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 128, 0), 1, cv2.LINE_AA)
    return out


def active_findings(findings: list[dict], t: float, window_s: float = FINDING_WINDOW_S) -> list[str]:
    """Textos dos achados cujo intervalo [t_start, t_end] ± window_s contém t."""
    out = []
    for f in findings:
        t0 = f.get("t_start", 0.0)
        t1 = f.get("t_end", t0)
        if t1 is None:
            t1 = t0
        if t0 - window_s <= t <= t1 + window_s:
            out.append(f.get("explanation") or f.get("type", ""))
    return out


def draw_overlay(img: np.ndarray, t: float, zones: dict, texts: list[str]) -> np.ndarray:
    """Desenha polígonos das zonas, o tempo no canto superior e os textos de achados em vermelho."""
    out = img.copy()
    h, w = out.shape[:2]
    for name, poly in zones.items():
        if not _is_polygon(poly):
            continue
        pts = np.array([[x * w, y * h] for x, y in poly], dtype=np.int32)
        cv2.polylines(out, [pts], True, ZONE_COLOR, 2)
        cv2.putText(out, name, tuple(pts[0] + [4, 16]), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    ZONE_COLOR, 1, cv2.LINE_AA)
    m, s = divmod(t, 60)
    cv2.putText(out, f"{int(m):02d}:{s:05.2f}", (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                WHITE, 2, cv2.LINE_AA)
    for k, text in enumerate(texts[:4]):
        cv2.putText(out, _ascii(text)[:90], (10, 52 + 24 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    RED, 2, cv2.LINE_AA)
    return out


def _is_polygon(v: object) -> bool:
    return (isinstance(v, list) and len(v) >= 3
            and all(isinstance(p, list | tuple) and len(p) == 2 for p in v))


def _ascii(text: str) -> str:
    """O OpenCV (Hershey) não desenha acentos; remove-os."""
    import unicodedata

    return (unicodedata.normalize("NFKD", text).replace("°", " graus")
            .encode("ascii", "ignore").decode("ascii"))


def to_browser_mp4(src: Path, dst: Path) -> Path:
    """Converte para H.264 yuv420p com faststart (reproduzível no navegador)."""
    cmd = ["ffmpeg", "-y", "-i", str(src), "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(dst)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("ffmpeg não encontrado no PATH") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg falhou: {stderr}") from exc
    return dst


class AnnotatedWriter:
    """Escreve frames com mp4v num arquivo temporário e converte para H.264 no `close()`."""

    def __init__(self, path: Path, fps: float, size: tuple[int, int]) -> None:
        self.path = Path(path)
        self.tmp = self.path.with_name(self.path.stem + ".tmp.mp4")
        self.size = size
        self.writer = cv2.VideoWriter(str(self.tmp), cv2.VideoWriter_fourcc(*"mp4v"),
                                      float(fps), size)
        if not self.writer.isOpened():
            raise RuntimeError(f"Não foi possível criar o vídeo {self.tmp}")

    def write(self, img: np.ndarray) -> None:
        """Escreve um frame BGR (redimensiona se preciso)."""
        if (img.shape[1], img.shape[0]) != self.size:
            img = cv2.resize(img, self.size)
        self.writer.write(img)

    def close(self) -> Path:
        """Fecha o arquivo e gera o MP4 H.264 final."""
        self.writer.release()
        try:
            to_browser_mp4(self.tmp, self.path)
        finally:
            self.tmp.unlink(missing_ok=True)
        return self.path
