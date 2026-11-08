"""Rotas de pacientes."""
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
