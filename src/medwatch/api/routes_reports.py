"""Rota de relatório do paciente."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException

from medwatch import db
from medwatch.api.deps import get_storage_dep
from medwatch.reports.render import build_patient_report, html_to_pdf
from medwatch.storage import Storage

router = APIRouter(tags=["reports"])


@router.post("/reports/patient/{patient_id}")
def patient_report(patient_id: str, storage: Storage = Depends(get_storage_dep)) -> dict:
    """Gera o relatório HTML/PDF do paciente e devolve as chaves no storage."""
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(404, "Paciente não encontrado")
    latest = db.latest_event_ts(patient_id) or datetime.now(UTC)
    since = latest - timedelta(hours=24)
    risks = db.query_risk(patient_id, since)
    alerts = [a for a in db.list_alerts(None, patient_id) if a["created_at"] >= since]
    html = build_patient_report(
        patient, risks[-1] if risks else None, alerts,
        db.list_evidence(patient_id, since, 500), db.query_vitals(patient_id, since))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    prefix = f"reports/{patient_id}/{stamp}"
    out = {"report_html": f"{prefix}.html"}
    storage.put_bytes(html.encode("utf-8"), out["report_html"])
    pdf = html_to_pdf(html)
    if pdf:
        out["report_pdf"] = f"{prefix}.pdf"
        storage.put_bytes(pdf, out["report_pdf"])
    return out
