"""Wrappers dos modelos YOLO de detecção e pose."""
from dataclasses import dataclass

import numpy as np


@dataclass
class Detection:
    """Detecção de objeto: classe, confiança e caixa em pixels."""

    cls: str
    conf: float
    xyxy: tuple[float, float, float, float]


@dataclass
class Person:
    """Pessoa com caixa, 17 keypoints COCO (pixels) e confiança por ponto."""

    track_id: int | None
    xyxy: tuple[float, float, float, float]
    keypoints: np.ndarray
    kp_conf: np.ndarray


class Detector:
    """Detector de objetos YOLO."""

    def __init__(self, weights: str):
        from ultralytics import YOLO

        self.model = YOLO(weights)

    def __call__(self, img) -> tuple[list[Detection], object]:
        """Detecta objetos; devolve detecções e o resultado bruto (para r.plot())."""
        r = self.model.predict(img, verbose=False, conf=0.35)[0]
        names = r.names
        dets = [
            Detection(names[int(c)], float(p), tuple(map(float, b)))
            for b, c, p in zip(
                r.boxes.xyxy.cpu().numpy(),
                r.boxes.cls.cpu().numpy(),
                r.boxes.conf.cpu().numpy(),
                strict=True,
            )
        ]
        return dets, r


class PoseEstimator:
    """Estimador de pose YOLO com tracking; use uma instância por vídeo."""

    def __init__(self, weights: str):
        from ultralytics import YOLO

        self.model = YOLO(weights)

    def __call__(self, img) -> tuple[list[Person], object]:
        """Estima poses no frame; devolve pessoas e o resultado bruto."""
        r = self.model.track(img, persist=True, verbose=False, conf=0.4)[0]
        people: list[Person] = []
        if r.keypoints is None or r.boxes is None:
            return people, r
        xy = r.keypoints.xy.cpu().numpy()
        conf = (
            r.keypoints.conf.cpu().numpy()
            if r.keypoints.conf is not None
            else np.ones(xy.shape[:2])
        )
        ids = (
            r.boxes.id.cpu().numpy().astype(int)
            if r.boxes.id is not None
            else [None] * len(xy)
        )
        for k, c, b, tid in zip(xy, conf, r.boxes.xyxy.cpu().numpy(), ids, strict=True):
            people.append(Person(tid, tuple(map(float, b)), k, c))
        return people, r


def main_person(people: list[Person]) -> Person | None:
    """Pessoa com a maior bbox (há um paciente principal por vídeo)."""
    if not people:
        return None
    return max(
        people,
        key=lambda p: max(0.0, p.xyxy[2] - p.xyxy[0]) * max(0.0, p.xyxy[3] - p.xyxy[1]),
    )
