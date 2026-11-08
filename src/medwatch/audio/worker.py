"""Worker de áudio: transcrição, linguagem, voz e sons respiratórios."""
from __future__ import annotations

import json
import logging
import tempfile
from datetime import timedelta
from pathlib import Path
from types import ModuleType

from medwatch import db as default_db
from medwatch.audio.acoustic import assess_voice, extract_features
from medwatch.audio.convert import to_wav_16k_mono
from medwatch.audio.language import LanguageAnalyzer, get_language_analyzer
from medwatch.audio.speech import Transcriber, get_transcriber
from medwatch.audio.terms import find_critical_terms
from medwatch.bus import Bus
from medwatch.config import get_settings, load_yaml
from medwatch.contracts import Evidence, MediaJob, Modality, Severity
from medwatch.logging_setup import setup_logging
from medwatch.storage import Storage, get_storage

log = logging.getLogger(__name__)

GROUP = "worker-audio"
STREAMS = ["jobs.audio"]
BASELINE_PATH = Path("data/references/voice_baseline.json")


def mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


def load_baseline(path: Path = BASELINE_PATH) -> dict | None:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


class AudioWorker:
    def __init__(self, bus: Bus, storage: Storage, db_module: ModuleType | object = default_db,
                 transcriber: Transcriber | None = None,
                 analyzer: LanguageAnalyzer | None = None,
                 detector=None, baseline: dict | None = None,
                 cfg: dict | None = None, terms_cfg: dict | None = None) -> None:
        cfg = cfg or load_yaml("thresholds")
        self.bus, self.storage, self.db = bus, storage, db_module
        self.transcriber = transcriber or get_transcriber()
        self.analyzer = analyzer or get_language_analyzer()
        self.voice_cfg = cfg["voice"]
        self.terms_cfg = terms_cfg or load_yaml("critical_terms")
        self.baseline = baseline if baseline is not None else load_baseline()
        if detector is None and not get_settings().audio_disable_events:
            from medwatch.audio.events import RespiratoryEventDetector
            detector = RespiratoryEventDetector(cfg["audio_events"])
        self.detector = detector

    def process(self, job: MediaJob) -> list[Evidence]:
        self.db.update_media(job.media_id, status="processing")
        try:
            evs = self._process(job)
        except Exception as exc:
            self.db.update_media(job.media_id, status="failed", error=str(exc))
            raise
        for e in evs:
            self.bus.publish("evidence", e)
        return evs

    def _ev(self, job: MediaJob, typ: str, score: float, sev: Severity, text: str,
            model: str, payload: dict, offset: float = 0.0) -> Evidence:
        return Evidence(
            patient_id=job.patient_id, modality=Modality.audio, type=typ,
            score=max(0.0, min(1.0, score)), severity=sev,
            ts_start=job.recorded_at + timedelta(seconds=offset), explanation=text,
            source_ref=f"media:{job.media_id}#t={int(offset)}", model_name=model, payload=payload)

    def _process(self, job: MediaJob) -> list[Evidence]:
        with tempfile.TemporaryDirectory() as tmp:
            raw = self.storage.get_to_path(job.storage_uri, Path(tmp) / "input")
            wav = to_wav_16k_mono(raw, Path(tmp) / "audio.wav")
            segments = self.transcriber.transcribe(wav)
            used = [(i, s) for i, s in enumerate(segments)
                    if job.patient_speaker is None or s.speaker == job.patient_speaker]
            lang = self.analyzer.analyze([s.text for _, s in used])
            feats = extract_features(wav, segments, job.patient_speaker)
            events = self.detector.detect(wav) if self.detector is not None else []

        evs: list[Evidence] = []
        terms_found: list[dict] = []
        seen: set[str] = set()
        for i, s in used:
            for h in find_critical_terms(s.text, self.terms_cfg):
                if h["term"] in seen:
                    continue
                seen.add(h["term"])
                terms_found.append({**h, "segment_index": i, "offset_s": s.offset_s})
                evs.append(self._ev(
                    job, "speech_critical_term", h["weight"], Severity.warning,
                    f"Paciente relatou '{h['term']}' ({mmss(s.offset_s)})",
                    "azure-speech+language",
                    {"term": h["term"], "category": h["category"], "segment_index": i},
                    s.offset_s))

        sents = lang.sentiments
        if sents:
            ratio = sum(1 for x in sents if x["sentiment"] == "negative") / len(sents)
            if ratio >= 0.5:
                evs.append(self._ev(
                    job, "speech_negative_sentiment", ratio, Severity.info,
                    f"{round(ratio * 100)}% das falas do paciente têm sentimento negativo",
                    "azure-speech+language", {"negative_ratio": ratio}))

        entities = [e for doc in lang.health_entities for e in doc]
        if entities:
            names = sorted({e["text"] for e in entities})
            evs.append(self._ev(
                job, "clinical_entity", 0.1, Severity.info,
                "Entidades clínicas mencionadas: " + ", ".join(names[:8]),
                "azure-speech+language", {"entities": entities}))

        for typ, score, flags in assess_voice(feats, self.baseline, self.voice_cfg):
            label = ("Sinais de fadiga na voz" if typ == "voice_fatigue"
                     else "Indicadores de disartria na voz")
            active = ", ".join(k for k, v in flags.items() if v and k != "baseline_missing")
            evs.append(self._ev(job, typ, score, Severity.warning, f"{label} ({active})",
                                "egemaps-rules", {"flags": flags, "features": feats}))

        for ev in events:
            first = ev["windows"][0]["t_start"]
            evs.append(self._ev(
                job, "respiratory_sound", ev["max_score"], Severity.warning,
                f"Som respiratório detectado: {ev['label']} ({mmss(first)})",
                "ast-audioset", {"label": ev["label"], "max_score": ev["max_score"],
                                 "windows": ev["windows"]}, first))

        analysis = {
            "sentiments": sents, "key_phrases": lang.key_phrases, "entities": lang.health_entities,
            "terms": terms_found, "features": feats, "sound_events": events,
        }
        segs = [{"speaker": s.speaker, "text": s.text, "offset_s": s.offset_s,
                 "duration_s": s.duration_s} for s in segments]
        self.db.insert_transcript(job.media_id, get_settings().speech_language, segs, analysis)
        key = f"artifacts/{job.media_id}/analysis.json"
        self.storage.put_bytes(json.dumps(analysis, ensure_ascii=False, default=str).encode(), key)
        self.db.update_media(job.media_id, status="done", artifacts={"analysis": key})
        return evs

    def handle(self, stream: str, payload: dict) -> None:
        self.process(MediaJob(**payload))


def main() -> None:
    setup_logging("worker-audio")
    worker = AudioWorker(Bus(), get_storage())
    log.info("worker-audio iniciado")
    worker.bus.consume(STREAMS, GROUP, worker.handle)


if __name__ == "__main__":
    main()
