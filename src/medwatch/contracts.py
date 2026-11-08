"""Contratos compartilhados (modelos Pydantic)."""
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Modality(StrEnum):
    video = "video"
    audio = "audio"
    text = "text"
    vitals = "vitals"
    prescription = "prescription"
    movement = "movement"

class Severity(StrEnum):
    info = "info"
    warning = "warning"
    critical = "critical"

SEVERITY_ORDER = {"none": 0, "info": 1, "warning": 2, "critical": 3}

class Evidence(BaseModel):
    evidence_id: UUID = Field(default_factory=uuid4)
    patient_id: str
    modality: Modality
    type: str                       # ver catálogo (seção 4)
    score: float = Field(ge=0.0, le=1.0)
    severity: Severity
    ts_start: datetime
    ts_end: datetime | None = None
    explanation: str                # frase em pt-BR, legível pelo médico
    source_ref: str | None = None   # ex.: "media:<uuid>#t=130" ou "vitals:P-0001@<ts>"
    model_name: str
    model_version: str = "0.1.0"
    payload: dict = Field(default_factory=dict)

class VitalObservation(BaseModel):
    patient_id: str
    ts: datetime
    hr: float | None = None         # bpm
    sbp: float | None = None        # mmHg
    dbp: float | None = None        # mmHg
    spo2: float | None = None       # %
    rr: float | None = None         # irpm
    temp: float | None = None       # °C
    consciousness: str = "A"        # A | C | V | P | U  (ACVPU)
    on_oxygen: bool = False

class PrescriptionEvent(BaseModel):
    rx_id: str
    patient_id: str
    ts: datetime
    drug: str
    dose: float | None = None
    unit: str | None = None
    route: str | None = None
    frequency: str | None = None
    action: str                     # start | change | stop

class MovementSample(BaseModel):
    patient_id: str
    ts: datetime                    # início do minuto
    activity_count: float           # 0..100, contagem normalizada no minuto
    in_bed: bool | None = None
    source: str                     # sensor | video

class MediaJob(BaseModel):
    media_id: UUID
    patient_id: str
    kind: str                       # video | audio | document
    storage_uri: str
    recorded_at: datetime
    mode: str | None = None         # vídeo: physio | surgery | bed
    exercise: str | None = None     # vídeo physio: chave de exercises.yaml
    camera: str | None = None       # chave de zones.yaml
    patient_speaker: str | None = None  # áudio: ex. "Guest-2"

class Alert(BaseModel):
    alert_id: UUID = Field(default_factory=uuid4)
    patient_id: str
    level: Severity
    risk_score: float               # 0..100
    title: str
    summary: str                    # texto multilinha pt-BR
    evidence_ids: list[UUID]
    status: str = "open"            # open | acknowledged | dismissed | resolved
    escalated: bool = False
    created_at: datetime
    updated_at: datetime
    event: str = "created"          # created | escalated | updated (só no stream)
