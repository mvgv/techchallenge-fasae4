"""Rotas de pacientes."""
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from medwatch import db

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientIn(BaseModel):
    patient_id: str
    display_name: str
    bed: str | None = None


@router.post("", status_code=201)
def create_patient(body: PatientIn) -> dict:
    db.upsert_patient(body.patient_id, body.display_name, body.bed)
    return db.get_patient(body.patient_id)


@router.get("")
def list_patients() -> list[dict]:
    return db.list_patients()


@router.get("/{patient_id}")
def get_patient(patient_id: str) -> dict:
    p = db.get_patient(patient_id)
    if p is None:
        raise HTTPException(404, "Paciente não encontrado")
    vitals = db.query_vitals(patient_id)
    p["latest_vitals"] = vitals[-1] if vitals else None
    return p


@router.get("/{patient_id}/vitals")
def get_vitals(patient_id: str, since: datetime | None = None,
               until: datetime | None = None) -> list[dict]:
    _require_patient(patient_id)
    if since is None:
        latest = db.latest_event_ts(patient_id)
        if latest is not None:
            since = latest - timedelta(hours=6)
    return db.query_vitals(patient_id, since, until)


@router.get("/{patient_id}/evidence")
def get_evidence(patient_id: str, since: datetime | None = None,
                 limit: int = 200) -> list[dict]:
    _require_patient(patient_id)
    return db.list_evidence(patient_id, since, limit)


@router.get("/{patient_id}/risk")
def get_risk(patient_id: str, since: datetime | None = None) -> list[dict]:
    _require_patient(patient_id)
    return db.query_risk(patient_id, since)


def _require_patient(patient_id: str) -> None:
    if db.get_patient(patient_id) is None:
        raise HTTPException(404, "Paciente não encontrado")
