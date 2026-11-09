"""Rotas de alertas: listagem e confirmação."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from medwatch import db

router = APIRouter(tags=["alerts"])


class AckIn(BaseModel):
    user: str
    decision: Literal["confirmed", "dismissed"]
    note: str | None = None


@router.get("/alerts")
def list_alerts(status: str | None = None, patient_id: str | None = None) -> list[dict]:
    return db.list_alerts(status, patient_id)


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: UUID, body: AckIn) -> dict:
    if db.get_alert(alert_id) is None:
        raise HTTPException(404, "Alerta não encontrado")
    new_status = "acknowledged" if body.decision == "confirmed" else "dismissed"
    row = db.ack_alert(alert_id, new_status, body.user, body.note)
    if row is None:
        raise HTTPException(409, "Alerta não está aberto")
    return row
