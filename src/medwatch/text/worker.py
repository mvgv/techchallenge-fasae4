"""Worker de texto: documentos .txt com termos críticos e entidades clínicas."""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from types import ModuleType

from medwatch import db as default_db
from medwatch.audio.language import LanguageAnalyzer, get_language_analyzer
from medwatch.audio.terms import find_critical_terms
from medwatch.bus import Bus
from medwatch.config import load_yaml
from medwatch.contracts import Evidence, MediaJob, Modality, Severity
from medwatch.logging_setup import setup_logging
from medwatch.storage import Storage, get_storage

log = logging.getLogger(__name__)

GROUP = "worker-text"
STREAMS = ["jobs.text"]
MAX_CHARS = 5000


def split_paragraphs(text: str, limit: int = MAX_CHARS) -> list[str]:
    """Divide em parágrafos; parágrafos maiores que `limit` são fatiados."""
    out: list[str] = []
    for p in (x.strip() for x in text.replace("\r\n", "\n").split("\n\n")):
        while len(p) > limit:
            cut = p.rfind(" ", 0, limit)
            cut = cut if cut > 0 else limit
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out


class TextWorker:
    def __init__(self, bus: Bus, storage: Storage, db_module: ModuleType | object = default_db,
                 analyzer: LanguageAnalyzer | None = None,
                 terms_cfg: dict | None = None) -> None:
        self.bus, self.storage, self.db = bus, storage, db_module
        self.analyzer = analyzer or get_language_analyzer()
        self.terms_cfg = terms_cfg or load_yaml("critical_terms")

    def _ev(self, job: MediaJob, typ: str, score: float, text: str, payload: dict,
            sev: Severity = Severity.warning) -> Evidence:
        return Evidence(patient_id=job.patient_id, modality=Modality.text, type=typ,
                        score=max(0.0, min(1.0, score)), severity=sev,
                        ts_start=job.recorded_at, explanation=text,
                        source_ref=f"media:{job.media_id}#t=0",
                        model_name="azure-language", payload=payload)

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

    def _process(self, job: MediaJob) -> list[Evidence]:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.storage.get_to_path(job.storage_uri, Path(tmp) / "doc.txt")
            text = path.read_text(encoding="utf-8", errors="replace")
        paragraphs = split_paragraphs(text)
        lang = self.analyzer.analyze(paragraphs)

        evs: list[Evidence] = []
        terms: list[dict] = []
        seen: set[str] = set()
        for i, p in enumerate(paragraphs):
            for h in find_critical_terms(p, self.terms_cfg):
                if h["term"] in seen:
                    continue
                seen.add(h["term"])
                terms.append({**h, "paragraph": i})
                evs.append(self._ev(
                    job, "text_critical_term", h["weight"],
                    f"Documento menciona '{h['term']}' (parágrafo {i + 1})",
                    {"term": h["term"], "category": h["category"]}))
        entities = [e for doc in lang.health_entities for e in doc]
        if entities:
            names = sorted({e["text"] for e in entities})
            evs.append(self._ev(
                job, "clinical_entity", 0.1,
                "Entidades clínicas no documento: " + ", ".join(names[:8]),
                {"entities": entities}, Severity.info))

        analysis = {"sentiments": lang.sentiments, "key_phrases": lang.key_phrases,
                    "entities": lang.health_entities, "terms": terms,
                    "paragraphs": len(paragraphs)}
        key = f"artifacts/{job.media_id}/analysis.json"
        self.storage.put_bytes(json.dumps(analysis, ensure_ascii=False).encode(), key)
        self.db.update_media(job.media_id, status="done", artifacts={"analysis": key})
        return evs

    def handle(self, stream: str, payload: dict) -> None:
        self.process(MediaJob(**payload))


def main() -> None:
    setup_logging("worker-text")
    worker = TextWorker(Bus(), get_storage())
    log.info("worker-text iniciado")
    worker.bus.consume(STREAMS, GROUP, worker.handle)


if __name__ == "__main__":
    main()
