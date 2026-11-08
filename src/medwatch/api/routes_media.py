"""Rotas de mídia, documentos e arquivos."""
import mimetypes
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from medwatch import db
from medwatch.api.deps import get_bus, get_storage_dep
from medwatch.bus import Bus
from medwatch.config import load_yaml
from medwatch.contracts import MediaJob
from medwatch.storage import Storage

router = APIRouter(tags=["media"])

EXTENSIONS = {
    "video": {".mp4", ".mov", ".avi", ".mkv"},
    "audio": {".wav", ".mp3", ".m4a", ".ogg"},
    "document": {".txt", ".md"},
}
STREAMS = {"video": "jobs.video", "audio": "jobs.audio", "document": "jobs.text"}
MODES = {"physio", "surgery", "bed"}


def _validate(kind: str, filename: str, mode: str | None, exercise: str | None,
              camera: str | None) -> str | None:
    """Valida os parâmetros e devolve a câmera efetiva."""
    if kind not in EXTENSIONS:
        raise HTTPException(422, "kind deve ser video, audio ou document")
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSIONS[kind]:
        raise HTTPException(
            422, f"Extensão '{ext}' inválida para {kind}; use {sorted(EXTENSIONS[kind])}")
    if kind != "video":
        return camera
    if mode not in MODES:
        raise HTTPException(422, "mode é obrigatório para vídeo: physio, surgery ou bed")
    if mode == "physio":
        if not exercise:
            raise HTTPException(422, "exercise é obrigatório quando mode=physio")
        if exercise not in load_yaml("exercises.yaml"):
            raise HTTPException(422, f"exercise desconhecido: {exercise}")
    return camera or ("default_surgery" if mode == "surgery" else "default_bed")


def _register(*, local_path: Path, name: str, patient_id: str, kind: str,
              mode: str | None, exercise: str | None, camera: str | None,
              patient_speaker: str | None, recorded_at: datetime | None,
              bus: Bus, storage: Storage) -> dict:
    media_id = uuid4()
    recorded_at = recorded_at or datetime.now(UTC)
    uri = storage.put_file(local_path, f"media/{patient_id}/{media_id}/{name}")
    db.insert_media({
        "media_id": media_id, "patient_id": patient_id, "kind": kind, "mode": mode,
        "exercise": exercise, "camera": camera, "storage_uri": uri,
        "original_name": name, "recorded_at": recorded_at, "status": "queued",
    })
    bus.publish(STREAMS[kind], MediaJob(
        media_id=media_id, patient_id=patient_id, kind=kind, storage_uri=uri,
        recorded_at=recorded_at, mode=mode, exercise=exercise, camera=camera,
        patient_speaker=patient_speaker))
    return {"media_id": str(media_id), "status": "queued"}


@router.post("/media", status_code=202)
def upload_media(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
    kind: str = Form(...),
    mode: str | None = Form(None),
    exercise: str | None = Form(None),
    camera: str | None = Form(None),
    patient_speaker: str | None = Form(None),
    recorded_at: datetime | None = Form(None),
    bus: Bus = Depends(get_bus),
    storage: Storage = Depends(get_storage_dep),
) -> dict:
    name = Path(file.filename or "").name
    camera = _validate(kind, name, mode, exercise, camera)
    if db.get_patient(patient_id) is None:
        raise HTTPException(404, "Paciente não encontrado")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / name
        with tmp_path.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        return _register(
            local_path=tmp_path, name=name, patient_id=patient_id, kind=kind,
            mode=mode, exercise=exercise, camera=camera,
            patient_speaker=patient_speaker, recorded_at=recorded_at,
            bus=bus, storage=storage)


class DocumentIn(BaseModel):
    patient_id: str
    text: str
    recorded_at: datetime | None = None
    title: str | None = None


@router.post("/documents", status_code=202)
def upload_document(
    body: DocumentIn,
    bus: Bus = Depends(get_bus),
    storage: Storage = Depends(get_storage_dep),
) -> dict:
    if db.get_patient(body.patient_id) is None:
        raise HTTPException(404, "Paciente não encontrado")
    stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in (body.title or "documento"))
    name = f"{stem[:60] or 'documento'}.txt"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / name
        tmp_path.write_text(body.text, encoding="utf-8")
        res = _register(
            local_path=tmp_path, name=name, patient_id=body.patient_id, kind="document",
            mode=None, exercise=None, camera=None, patient_speaker=None,
            recorded_at=body.recorded_at, bus=bus, storage=storage)
    return {"media_id": res["media_id"]}


@router.get("/media")
def list_media(patient_id: str | None = None) -> list[dict]:
    return db.list_media(patient_id)


@router.get("/media/{media_id}")
def get_media(media_id: str) -> dict:
    try:
        m = db.get_media(media_id)
    except Exception:
        m = None
    if m is None:
        raise HTTPException(404, "Mídia não encontrada")
    m["transcript"] = db.get_transcript(media_id)
    return m


@router.get("/files/{key:path}")
def get_file(key: str, storage: Storage = Depends(get_storage_dep)):
    if ".." in Path(key).parts or key.startswith("/"):
        raise HTTPException(400, "Caminho inválido")
    try:
        stream = storage.open_stream(key)
        first = next(stream, None)
    except Exception as e:
        raise HTTPException(404, "Arquivo não encontrado") from e

    def gen():
        if first is not None:
            yield first
        yield from stream

    return StreamingResponse(
        gen(), media_type=mimetypes.guess_type(key)[0] or "application/octet-stream")
