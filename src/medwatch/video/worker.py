"""Worker de vídeo: pose/detecção, análise por modo, vídeo anotado e evidências."""
from __future__ import annotations

import json
import logging
import tempfile
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from types import ModuleType

import cv2

from medwatch import db as default_db
from medwatch.bus import Bus
from medwatch.config import get_settings, load_yaml
from medwatch.contracts import Evidence, MediaJob, Modality, MovementSample, Severity
from medwatch.logging_setup import setup_logging
from medwatch.reports.render import build_session_report
from medwatch.storage import Storage, get_storage
from medwatch.video.annotate import AnnotatedWriter, active_findings, base_image, draw_overlay
from medwatch.video.bed import analyze_bed
from medwatch.video.frames import iter_frames, video_info
from medwatch.video.models import Detector, PoseEstimator, fallback_person, main_person
from medwatch.video.physio import analyze_physio
from medwatch.video.surgery import analyze_surgery

log = logging.getLogger(__name__)

GROUP = "worker-video"
STREAMS = ["jobs.video"]
REFERENCES_DIR = Path("data/references")
MODES = ("physio", "bed", "surgery")

# Severidade típica do catálogo (seção 4); o achado pode sobrescrever com "severity".
SEVERITY = {
    "fall_detected": Severity.critical,
    "bed_exit_video": Severity.warning,
    "physio_low_rom": Severity.info,
    "physio_asymmetry": Severity.info,
    "physio_pattern_deviation": Severity.info,
    "physio_trunk_compensation": Severity.info,
    "physio_trunk_insufficient": Severity.info,
    "physio_rotation_low": Severity.info,
    "physio_incomplete": Severity.info,
    "surgery_zone_intrusion": Severity.warning,
    "surgery_instrument_out_of_zone": Severity.warning,
    "surgery_instrument_count_mismatch": Severity.critical,
}


def load_reference(exercise: str | None, ref_dir: Path = REFERENCES_DIR) -> dict | None:
    """Carrega data/references/<exercise>.json, se existir."""
    if not exercise:
        return None
    path = ref_dir / f"{exercise}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _catalog_payload(f: dict) -> dict:
    """Completa o payload com os campos obrigatórios do catálogo (seção 4)."""
    p = dict(f.get("payload") or {})
    t = f["type"]
    if f.get("rep") is not None:
        p.setdefault("rep", f["rep"])
    if t == "physio_low_rom":
        p.setdefault("ref_rom", p.get("reference_rom"))
    elif t == "physio_asymmetry":
        p.setdefault("joint_pair", p.get("pair"))
    elif t == "physio_pattern_deviation":
        p.setdefault("threshold", p.get("dtw_max"))
    elif t in ("physio_trunk_compensation", "physio_trunk_insufficient"):
        p.setdefault("trunk_deg", p.get("max_trunk_deg"))
    elif t == "surgery_zone_intrusion":
        p.setdefault("zone", "sterile_field")
        p.setdefault("max", p.get("max_people"))
        p.setdefault("people", p.get("max_people", 0) + 1)
    elif t == "surgery_instrument_out_of_zone":
        p.setdefault("cls", None)
        p.setdefault("seconds", float(f["t_end"] - f["t_start"]))
    elif t == "surgery_instrument_count_mismatch":
        p.setdefault("start_count", p.get("count_start"))
        p.setdefault("end_count", p.get("count_end"))
    return p


class VideoWorker:
    """Processa `MediaJob` de vídeo nos modos physio, bed e surgery."""

    def __init__(self, bus: Bus, storage: Storage, db_module: ModuleType | object = default_db,
                 pose_factory: Callable[[], object] | None = None,
                 detector: object | None = None,
                 detector_factory: Callable[[], object] | None = None,
                 thresholds: dict | None = None, exercises: dict | None = None,
                 zones: dict | None = None, target_fps: int | None = None,
                 ref_dir: Path = REFERENCES_DIR) -> None:
        s = get_settings()
        self.bus, self.storage, self.db = bus, storage, db_module
        self.pose_factory = pose_factory or (lambda: PoseEstimator(s.yolo_pose_weights))
        self._detector = detector
        self.detector_factory = detector_factory or (lambda: Detector(s.yolo_det_weights))
        self.thr = (thresholds or load_yaml("thresholds"))["video"]
        self.exercises = exercises if exercises is not None else load_yaml("exercises")
        self.zones_cfg = zones if zones is not None else load_yaml("zones")
        self.target_fps = target_fps or s.video_target_fps
        self.ref_dir = ref_dir

    @property
    def detector(self) -> object:
        """Detector compartilhado entre vídeos (criado sob demanda)."""
        if self._detector is None:
            self._detector = self.detector_factory()
        return self._detector

    def process(self, job: MediaJob) -> list[Evidence]:
        """Processa o job, atualiza o status da mídia e publica as evidências."""
        self.db.update_media(job.media_id, status="processing")
        try:
            evs = self._process(job)
        except Exception as exc:
            self.db.update_media(job.media_id, status="failed", error=str(exc))
            raise
        for e in evs:
            self.bus.publish("evidence", e)
        return evs

    def handle(self, stream: str, payload: dict) -> None:
        """Handler do consumidor do barramento."""
        self.process(MediaJob(**payload))

    def _report(self, media: dict, doc: dict) -> dict:
        """Gera o relatório da sessão; falha no relatório não derruba o processamento."""
        try:
            return build_session_report(media, doc, self.storage)
        except Exception:
            log.exception("Falha ao gerar relatório da sessão")
            return {}

    def _zones(self, job: MediaJob, mode: str) -> dict:
        key = job.camera or f"default_{mode}"
        if key not in self.zones_cfg:
            log.warning("zona %s não encontrada em zones.yaml; usando default_%s", key, mode)
            key = f"default_{mode}"
        return dict(self.zones_cfg.get(key) or {})

    def _process(self, job: MediaJob) -> list[Evidence]:
        mode = job.mode or "physio"
        if mode not in MODES:
            raise ValueError(f"Modo de vídeo desconhecido: {mode}")
        exercise_cfg = None
        if mode == "physio":
            if not job.exercise or job.exercise not in self.exercises:
                raise ValueError(f"Exercício desconhecido: {job.exercise}")
            exercise_cfg = self.exercises[job.exercise]
        zones = self._zones(job, mode) if mode != "physio" else {}
        prefix = f"artifacts/{job.media_id}"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            src = self.storage.get_to_path(job.storage_uri, tmp / "input")
            info = video_info(src)
            w, h = info["width"], info["height"]
            src_fps = info["fps"] or 30.0
            eff_fps = src_fps / max(1, round(src_fps / self.target_fps))

            # Passagem 1: modelos + frames com a anotação do Ultralytics em vídeo temporário.
            pose = self.pose_factory()
            det = self.detector if mode == "surgery" else None
            # T41: no leito, quadro sem pose usa a caixa do detector de pessoas
            fb_conf = (self.thr.get("fall") or {}).get("detector_fallback_conf") \
                if mode == "bed" else None
            people_all, dets_all, times = [], [], []
            base_path = tmp / "base.avi"
            base = cv2.VideoWriter(str(base_path), cv2.VideoWriter_fourcc(*"MJPG"), eff_fps, (w, h))
            try:
                for fr in iter_frames(src, self.target_fps):
                    people, pose_r = pose(fr.image)
                    dets, det_r = det(fr.image) if det is not None else ([], None)
                    if fb_conf is not None and not people:
                        fb = fallback_person(self.detector(fr.image, conf=fb_conf)[0], fb_conf)
                        people = [fb] if fb is not None else []
                    people_all.append(people)
                    dets_all.append(dets)
                    times.append(fr.t)
                    img = base_image(fr.image, pose_r, det_r)
                    if (img.shape[1], img.shape[0]) != (w, h):
                        img = cv2.resize(img, (w, h))
                    base.write(img)
            finally:
                base.release()
            if not times:
                raise RuntimeError("Vídeo sem frames legíveis")

            # Análise do modo.
            analysis, findings, extra = self._analyze(
                mode, people_all, dets_all, times, eff_fps, w, h, zones, exercise_cfg,
                job.exercise)

            # Passagem 2: sobreposição de zonas, tempo e achados; frames-chave.
            key_idx = {f["frame_index"]: f for f in findings if f.get("frame_index") is not None}
            frame_keys: dict[int, str] = {}
            out_path = tmp / "annotated.mp4"
            writer = AnnotatedWriter(out_path, eff_fps, (w, h))
            cap = cv2.VideoCapture(str(base_path))
            try:
                k = 0
                while k < len(times):
                    ok, img = cap.read()
                    if not ok:
                        break
                    t = times[k]
                    img = draw_overlay(img, t, zones, active_findings(findings, t))
                    writer.write(img)
                    if k in key_idx:
                        f = key_idx[k]
                        kind = f["type"].split("_")[0]
                        key = f"{prefix}/{kind}_{t:.1f}.jpg"
                        okj, buf = cv2.imencode(".jpg", img)
                        if okj:
                            self.storage.put_bytes(buf.tobytes(), key)
                            frame_keys[k] = key
                    k += 1
            finally:
                cap.release()
                writer.close()
            annotated_key = f"{prefix}/annotated.mp4"
            self.storage.put_file(out_path, annotated_key)

        for f in findings:
            if f.get("frame_index") in frame_keys:
                f["frame_key"] = frame_keys[f["frame_index"]]
                f.setdefault("payload", {})["frame_key"] = f["frame_key"]

        doc = {
            "media_id": str(job.media_id), "patient_id": job.patient_id, "mode": mode,
            "exercise": job.exercise, "camera": job.camera, "video": info,
            "analysis_fps": eff_fps, "n_frames": len(times), "findings": findings,
            "key_frames": sorted(frame_keys.values()), **analysis,
        }
        findings_key = f"{prefix}/findings.json"
        self.storage.put_bytes(
            json.dumps(doc, ensure_ascii=False, default=str).encode("utf-8"), findings_key)

        model = "yolov8n+rules" if mode == "surgery" else "yolov8n-pose+rules"
        evs = [self._evidence(job, f, model) for f in findings]

        if mode == "bed":
            for start_s, act, in_bed in extra:
                self.bus.publish("movement", MovementSample(
                    patient_id=job.patient_id, ts=job.recorded_at + timedelta(seconds=start_s),
                    activity_count=act, in_bed=in_bed, source="video"))

        media = {"media_id": str(job.media_id), "patient_id": job.patient_id, "mode": mode,
                 "exercise": job.exercise, "recorded_at": job.recorded_at}
        self.db.update_media(job.media_id, status="done", artifacts={
            "annotated": annotated_key, "findings": findings_key,
            **self._report(media, doc)})
        return evs

    def _analyze(self, mode, people_all, dets_all, times, fps, w, h, zones, exercise_cfg,
                 exercise) -> tuple[dict, list[dict], list]:
        mains = [main_person(ps) for ps in people_all]
        if mode == "physio":
            ref = load_reference(exercise, self.ref_dir)
            r = analyze_physio(mains, times, fps, exercise_cfg, ref, self.thr)
            return ({"reps": r.reps, "series": r.series, "reference_used": ref is not None},
                    r.findings, [])
        if mode == "bed":
            r = analyze_bed(mains, times, w, h, zones, self.thr)
            act = [list(x) for x in r.activity_per_minute]
            return {"activity_per_minute": act}, r.findings, r.activity_per_minute
        r = analyze_surgery(dets_all, people_all, times, w, h, zones, self.thr)
        return {}, r.findings, []

    def _evidence(self, job: MediaJob, f: dict, model: str) -> Evidence:
        sev = Severity(f["severity"]) if f.get("severity") else SEVERITY[f["type"]]
        t0 = float(f["t_start"])
        t1 = f.get("t_end")
        return Evidence(
            patient_id=job.patient_id, modality=Modality.video, type=f["type"],
            score=max(0.0, min(1.0, float(f["score"]))), severity=sev,
            ts_start=job.recorded_at + timedelta(seconds=t0),
            ts_end=None if t1 is None else job.recorded_at + timedelta(seconds=float(t1)),
            explanation=f["explanation"], source_ref=f"media:{job.media_id}#t={int(t0)}",
            model_name=model, payload=_catalog_payload(f))


def main() -> None:
    """Ponto de entrada do container worker-video."""
    setup_logging("worker-video")
    worker = VideoWorker(Bus(), get_storage())
    log.info("worker-video iniciado")
    worker.bus.consume(STREAMS, GROUP, worker.handle)


if __name__ == "__main__":
    main()
