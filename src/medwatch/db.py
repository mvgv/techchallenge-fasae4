"""Camada de acesso ao PostgreSQL/TimescaleDB (SQLAlchemy Core com text())."""
import json
from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import Engine, create_engine, text

from medwatch.config import get_settings
from medwatch.contracts import (
    Alert,
    Evidence,
    MovementSample,
    PrescriptionEvent,
    VitalObservation,
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def _rows(sql: str, **params: Any) -> list[dict]:
    with get_engine().connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _one(sql: str, **params: Any) -> dict | None:
    rows = _rows(sql, **params)
    return rows[0] if rows else None


def _exec(sql: str, **params: Any) -> None:
    with get_engine().begin() as conn:
        conn.execute(text(sql), params)


def _j(value: Any) -> str:
    return json.dumps(value, default=str)


def ping() -> bool:
    try:
        _exec("SELECT 1")
        return True
    except Exception:
        return False


# ---------- pacientes ----------

def upsert_patient(patient_id: str, display_name: str, bed: str | None) -> None:
    _exec(
        """INSERT INTO patients (patient_id, display_name, bed)
           VALUES (:pid, :name, :bed)
           ON CONFLICT (patient_id) DO UPDATE
           SET display_name = EXCLUDED.display_name, bed = EXCLUDED.bed""",
        pid=patient_id, name=display_name, bed=bed,
    )


_PATIENT_SELECT = """
SELECT p.patient_id, p.display_name, p.bed, p.created_at,
  (SELECT r.risk_score FROM risk_snapshots r WHERE r.patient_id = p.patient_id
     ORDER BY r.ts DESC LIMIT 1) AS latest_risk,
  (SELECT r.level FROM risk_snapshots r WHERE r.patient_id = p.patient_id
     ORDER BY r.ts DESC LIMIT 1) AS latest_level,
  (SELECT count(*) FROM alerts a WHERE a.patient_id = p.patient_id
     AND a.status = 'open') AS open_alerts
FROM patients p
"""


def list_patients() -> list[dict]:
    return _rows(_PATIENT_SELECT + " ORDER BY p.patient_id")


def get_patient(patient_id: str) -> dict | None:
    return _one(_PATIENT_SELECT + " WHERE p.patient_id = :pid", pid=patient_id)


# ---------- mídia ----------

def insert_media(row: dict) -> None:
    _exec(
        """INSERT INTO media (media_id, patient_id, kind, mode, exercise, camera,
                              storage_uri, original_name, recorded_at, status, artifacts)
           VALUES (:media_id, :patient_id, :kind, :mode, :exercise, :camera,
                   :storage_uri, :original_name, :recorded_at,
                   COALESCE(:status, 'queued'), CAST(:artifacts AS JSONB))""",
        media_id=str(row["media_id"]),
        patient_id=row["patient_id"],
        kind=row["kind"],
        mode=row.get("mode"),
        exercise=row.get("exercise"),
        camera=row.get("camera"),
        storage_uri=row["storage_uri"],
        original_name=row.get("original_name"),
        recorded_at=row["recorded_at"],
        status=row.get("status"),
        artifacts=_j(row.get("artifacts") or {}),
    )


def update_media(media_id, *, status: str | None = None, error: str | None = None,
                 artifacts: dict | None = None) -> None:
    sets, params = [], {"mid": str(media_id)}
    if status is not None:
        sets.append("status = :status")
        params["status"] = status
    if error is not None:
        sets.append("error = :error")
        params["error"] = error
    if artifacts is not None:
        sets.append("artifacts = artifacts || CAST(:new AS JSONB)")
        params["new"] = _j(artifacts)
    if not sets:
        return
    _exec(f"UPDATE media SET {', '.join(sets)} WHERE media_id = :mid", **params)


def get_media(media_id) -> dict | None:
    return _one("SELECT * FROM media WHERE media_id = :mid", mid=str(media_id))


def list_media(patient_id: str | None) -> list[dict]:
    return _rows(
        """SELECT * FROM media WHERE (CAST(:pid AS TEXT) IS NULL OR patient_id = :pid)
           ORDER BY recorded_at DESC""",
        pid=patient_id,
    )


# ---------- séries temporais ----------

def insert_vital(obs: VitalObservation, news2: int | None) -> None:
    _exec(
        """INSERT INTO vitals (patient_id, ts, hr, sbp, dbp, spo2, rr, temp,
                               consciousness, on_oxygen, news2)
           VALUES (:patient_id, :ts, :hr, :sbp, :dbp, :spo2, :rr, :temp,
                   :consciousness, :on_oxygen, :news2)
           ON CONFLICT DO NOTHING""",
        **obs.model_dump(), news2=news2,
    )


def insert_prescription(ev: PrescriptionEvent, drug_norm: str) -> None:
    _exec(
        """INSERT INTO prescriptions (rx_id, patient_id, ts, drug, drug_norm, dose,
                                      unit, route, frequency, action)
           VALUES (:rx_id, :patient_id, :ts, :drug, :drug_norm, :dose,
                   :unit, :route, :frequency, :action)
           ON CONFLICT DO NOTHING""",
        **ev.model_dump(), drug_norm=drug_norm,
    )


def insert_movement(s: MovementSample) -> None:
    _exec(
        """INSERT INTO movement (patient_id, ts, activity_count, in_bed, source)
           VALUES (:patient_id, :ts, :activity_count, :in_bed, :source)
           ON CONFLICT DO NOTHING""",
        **s.model_dump(),
    )


def query_vitals(patient_id: str, since: datetime | None = None,
                 until: datetime | None = None) -> list[dict]:
    return _rows(
        """SELECT * FROM vitals WHERE patient_id = :pid
             AND (CAST(:since AS TIMESTAMPTZ) IS NULL OR ts >= :since)
             AND (CAST(:until AS TIMESTAMPTZ) IS NULL OR ts <= :until)
           ORDER BY ts""",
        pid=patient_id, since=since, until=until,
    )


def latest_event_ts(patient_id: str) -> datetime | None:
    row = _one("SELECT max(ts) AS ts FROM vitals WHERE patient_id = :pid", pid=patient_id)
    return row["ts"] if row else None


# ---------- transcrições ----------

def insert_transcript(media_id, language: str, segments: list, analysis: dict) -> None:
    _exec(
        """INSERT INTO transcripts (media_id, language, segments, analysis)
           VALUES (:mid, :lang, CAST(:seg AS JSONB), CAST(:ana AS JSONB))
           ON CONFLICT (media_id) DO UPDATE
           SET language = EXCLUDED.language, segments = EXCLUDED.segments,
               analysis = EXCLUDED.analysis""",
        mid=str(media_id), lang=language, seg=_j(segments), ana=_j(analysis),
    )


def get_transcript(media_id) -> dict | None:
    return _one("SELECT * FROM transcripts WHERE media_id = :mid", mid=str(media_id))


# ---------- evidências ----------

def insert_evidence(ev: Evidence) -> None:
    d = ev.model_dump(mode="json")
    d["payload"] = _j(ev.payload)
    d["ts_start"], d["ts_end"] = ev.ts_start, ev.ts_end
    _exec(
        """INSERT INTO evidence (evidence_id, patient_id, modality, type, score, severity,
                                 ts_start, ts_end, explanation, source_ref, model_name,
                                 model_version, payload)
           VALUES (:evidence_id, :patient_id, :modality, :type, :score, :severity,
                   :ts_start, :ts_end, :explanation, :source_ref, :model_name,
                   :model_version, CAST(:payload AS JSONB))
           ON CONFLICT DO NOTHING""",
        **d,
    )


def _evidence_from_row(r: dict) -> Evidence:
    return Evidence(**{k: r[k] for k in Evidence.model_fields})


def list_evidence(patient_id: str, since: datetime | None = None, limit: int = 100) -> list[dict]:
    return _rows(
        """SELECT * FROM evidence WHERE patient_id = :pid
             AND (CAST(:since AS TIMESTAMPTZ) IS NULL OR ts_start >= :since)
           ORDER BY ts_start DESC LIMIT :limit""",
        pid=patient_id, since=since, limit=limit,
    )


def recent_evidence_all(window_minutes: int) -> list[Evidence]:
    rows = _rows(
        """SELECT e.* FROM evidence e
           JOIN (SELECT patient_id, max(ts_start) AS m FROM evidence GROUP BY patient_id) x
             ON x.patient_id = e.patient_id
           WHERE e.ts_start >= x.m - make_interval(mins => :w)
           ORDER BY e.ts_start""",
        w=window_minutes,
    )
    return [_evidence_from_row(r) for r in rows]


def get_evidence_many(ids: list) -> list[dict]:
    if not ids:
        return []
    return _rows(
        "SELECT * FROM evidence WHERE evidence_id = ANY(CAST(:ids AS UUID[])) ORDER BY ts_start",
        ids=[str(i) for i in ids],
    )


# ---------- risco ----------

def insert_risk_snapshot(patient_id, ts, risk, level, contributions: dict) -> None:
    _exec(
        """INSERT INTO risk_snapshots (patient_id, ts, risk_score, level, contributions)
           VALUES (:pid, :ts, :risk, :level, CAST(:c AS JSONB))
           ON CONFLICT (patient_id, ts) DO UPDATE
           SET risk_score = EXCLUDED.risk_score, level = EXCLUDED.level,
               contributions = EXCLUDED.contributions""",
        pid=patient_id, ts=ts, risk=risk, level=str(level), c=_j(contributions),
    )


def query_risk(patient_id: str, since: datetime | None = None) -> list[dict]:
    return _rows(
        """SELECT * FROM risk_snapshots WHERE patient_id = :pid
             AND (CAST(:since AS TIMESTAMPTZ) IS NULL OR ts >= :since)
           ORDER BY ts""",
        pid=patient_id, since=since,
    )


# ---------- alertas ----------

def get_open_alert(patient_id: str) -> dict | None:
    return _one(
        """SELECT * FROM alerts WHERE patient_id = :pid AND status = 'open'
           ORDER BY created_at DESC LIMIT 1""",
        pid=patient_id,
    )


def last_closed_alert(patient_id: str) -> dict | None:
    return _one(
        """SELECT * FROM alerts WHERE patient_id = :pid AND status <> 'open'
           ORDER BY updated_at DESC LIMIT 1""",
        pid=patient_id,
    )


def insert_alert(a: Alert, event_ts: datetime) -> None:
    _exec(
        """INSERT INTO alerts (alert_id, patient_id, level, risk_score, title, summary,
                               evidence_ids, status, escalated, event_ts, created_at, updated_at)
           VALUES (:alert_id, :patient_id, :level, :risk_score, :title, :summary,
                   CAST(:evidence_ids AS UUID[]), :status, :escalated, :event_ts,
                   :created_at, :updated_at)""",
        alert_id=str(a.alert_id), patient_id=a.patient_id, level=str(a.level),
        risk_score=a.risk_score, title=a.title, summary=a.summary,
        evidence_ids=[str(i) for i in a.evidence_ids], status=a.status,
        escalated=a.escalated, event_ts=event_ts,
        created_at=a.created_at, updated_at=a.updated_at,
    )


_ALERT_FIELDS = {
    "level", "risk_score", "title", "summary", "status", "escalated",
    "acked_by", "acked_at", "ack_note",
}


def update_alert(alert_id, **fields) -> dict:
    sets, params = ["updated_at = now()"], {"aid": str(alert_id)}
    for k, v in fields.items():
        if k == "evidence_ids":
            sets.append("evidence_ids = CAST(:evidence_ids AS UUID[])")
            params[k] = [str(i) for i in v]
        elif k in _ALERT_FIELDS:
            sets.append(f"{k} = :{k}")
            params[k] = str(v) if k == "level" else v
        else:
            raise ValueError(f"campo de alerta inválido: {k}")
    with get_engine().begin() as conn:
        res = conn.execute(
            text(f"UPDATE alerts SET {', '.join(sets)} WHERE alert_id = :aid RETURNING *"),
            params,
        ).mappings().first()
    row = dict(res) if res else None
    if row is None:
        raise KeyError(f"alerta não encontrado: {alert_id}")
    return row


def list_alerts(status: str | None = None, patient_id: str | None = None) -> list[dict]:
    return _rows(
        """SELECT * FROM alerts
           WHERE (CAST(:status AS TEXT) IS NULL OR status = :status)
             AND (CAST(:pid AS TEXT) IS NULL OR patient_id = :pid)
           ORDER BY created_at DESC""",
        status=status, pid=patient_id,
    )


def alerts_to_escalate(minutes: int) -> list[dict]:
    return _rows(
        """SELECT * FROM alerts
           WHERE status = 'open' AND level = 'critical' AND NOT escalated
             AND created_at < now() - make_interval(mins => :m)
           ORDER BY created_at""",
        m=minutes,
    )
