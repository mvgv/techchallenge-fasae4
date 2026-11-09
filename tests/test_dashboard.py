"""Testes do dashboard: cliente da API, funções puras e smoke das telas (AppTest)."""
import json
from pathlib import Path

import httpx
import pytest

from medwatch.dashboard import api_client
from medwatch.dashboard.api_client import ApiClient

APP = Path(__file__).resolve().parents[1] / "src" / "medwatch" / "dashboard" / "app.py"

PATIENTS = [
    {"patient_id": "P-0001", "display_name": "Ana", "bed": "L1", "latest_risk": 25.0,
     "latest_level": "info", "open_alerts": 0},
    {"patient_id": "P-0002", "display_name": "Bruno", "bed": "L2", "latest_risk": 82.4,
     "latest_level": "critical", "open_alerts": 1},
]
ALERT = {"alert_id": "11111111-1111-1111-1111-111111111111", "patient_id": "P-0002",
         "level": "critical", "risk_score": 82.4, "title": "Risco crítico", "summary": "SpO2 baixa",
         "status": "open", "escalated": False, "event_ts": "2026-11-08T10:00:00+00:00"}


def _client(handler, errors=None):
    errors = errors if errors is not None else []
    return ApiClient("http://api:8000", transport=httpx.MockTransport(handler),
                     on_error=errors.append), errors


# ---------------------------------------------------------------- ApiClient

def test_client_builds_requests():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/alerts/abc/ack":
            return httpx.Response(200, json={"status": "acknowledged", **json.loads(req.content)})
        if req.url.path.startswith("/files/"):
            return httpx.Response(200, content=b"\x00bytes")
        return httpx.Response(200, json=[{"ok": True}])

    api, errors = _client(handler)
    assert api.list_alerts(status="open") == [{"ok": True}]
    assert seen[-1].url.params["status"] == "open"
    assert "patient_id" not in seen[-1].url.params
    api.get_vitals("P-0001", since="2026-11-08T00:00:00+00:00")
    assert seen[-1].url.path == "/patients/P-0001/vitals"
    assert "until" not in seen[-1].url.params
    ack = api.ack_alert("abc", "confirmed", note="")
    assert ack["user"] == "medico.demo" and ack["decision"] == "confirmed" and ack["note"] is None
    assert api.get_file("artifacts/m1/annotated.mp4") == b"\x00bytes"
    assert seen[-1].url.path == "/files/artifacts/m1/annotated.mp4"
    assert errors == []


def test_client_upload_is_multipart_without_empty_fields():
    seen = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(202, json={"media_id": "m1", "status": "queued"})

    api, _ = _client(handler)
    resp = api.upload_media(filename="a.wav", content=b"RIFF", patient_id="P-0001", kind="audio",
                            patient_speaker="Guest-2")
    assert resp == {"media_id": "m1", "status": "queued"}
    body = seen[0].read().decode("latin-1")
    assert seen[0].headers["content-type"].startswith("multipart/form-data")
    assert 'name="patient_speaker"' in body and 'name="mode"' not in body
    assert 'filename="a.wav"' in body


def test_client_reports_api_error_detail():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/ack"):
            return httpx.Response(409, json={"detail": "Alerta não está aberto"})
        return httpx.Response(422, json={"detail": [{"msg": "campo obrigatório"}]})

    api, errors = _client(handler)
    assert api.ack_alert("x", "dismissed") is None
    assert "409" in errors[-1] and "Alerta não está aberto" in errors[-1]
    assert api.list_media() is None
    assert "campo obrigatório" in errors[-1]


def test_client_reports_connection_error():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=req)

    api, errors = _client(handler)
    assert api.list_patients() is None
    assert "Falha ao acessar a API" in errors[0]


# ---------------------------------------------------------------- funções puras

def test_pure_helpers():
    from medwatch.dashboard import app

    assert app.level_chip("critical") == ":red-background[crítico]"
    assert app.level_chip("warning") == ":orange-background[atenção]"
    assert app.level_chip("info") == ":blue-background[informativo]"
    assert "normal" in app.level_chip(None)
    assert app.risk_pct(None) == 0 and app.risk_pct(140) == 100 and app.risk_pct(41.6) == 42
    assert [p["patient_id"] for p in app.sort_patients(PATIENTS)] == ["P-0002", "P-0001"]
    assert app.report_keys({"report_html": "a.html"}) == ("a.html", None)
    assert app.report_keys({"html_key": "a.html", "pdf_key": "a.pdf"}) == ("a.html", "a.pdf")
    assert app.mmss(75.4) == "01:15"


def test_highlight_terms_ignores_accent_and_case():
    from medwatch.dashboard.app import highlight_terms

    out = highlight_terms("Estou com Falta de ar e dor no peito, sem tontura.",
                          ["falta de ar", "dor no peito", "tontura"])
    assert out == "Estou com **Falta de ar** e **dor no peito**, sem **tontura**."
    assert highlight_terms("Sinto câimbra", ["caimbra"]) == "Sinto **câimbra**"
    assert highlight_terms("dorzinha", ["dor"]) == "dorzinha"


def test_transcript_rows_aligns_sentiment_with_patient_segments():
    from medwatch.dashboard.app import transcript_rows

    transcript = {
        "segments": [{"speaker": "Guest-1", "text": "Como está?", "offset_s": 0},
                     {"speaker": "Guest-2", "text": "Com dor no peito", "offset_s": 3}],
        "analysis": {"sentiments": [{"sentiment": "negative"}],
                     "terms": [{"term": "dor no peito", "segment_index": 1}]},
    }
    rows = transcript_rows(transcript, patient_speaker="Guest-2")
    assert rows[0]["sentiment"] is None
    assert rows[1]["sentiment"] == "negative"
    assert rows[1]["text"] == "Com **dor no peito**"


def test_evidence_table_uses_pt_labels():
    from medwatch.dashboard.app import evidence_table

    df = evidence_table([{"ts_start": "2026-11-08T10:00:00+00:00", "modality": "vitals",
                          "type": "news2_high", "score": 0.91, "explanation": "NEWS2 = 8"}],
                        {"news2_high": "NEWS2 alto"})
    assert list(df.columns) == ["hora", "modalidade", "tipo", "score", "explicação"]
    assert df.iloc[0]["tipo"] == "NEWS2 alto" and df.iloc[0]["modalidade"] == "Sinais vitais"


# ---------------------------------------------------------------- smoke das telas

class FakeApi:
    """API falsa em memória para o AppTest."""

    acks: list = []

    def __init__(self, *a, **kw):
        pass

    def list_patients(self):
        return PATIENTS

    def list_alerts(self, status=None, patient_id=None):
        return [] if FakeApi.acks else [ALERT]

    def ack_alert(self, alert_id, decision, user="medico.demo", note=None):
        FakeApi.acks.append((alert_id, decision, user, note))
        return {**ALERT, "status": "acknowledged"}

    def get_vitals(self, pid, since=None, until=None):
        return [{"ts": f"2026-11-08T10:0{i}:00+00:00", "hr": 80 + i, "spo2": 97, "rr": 16}
                for i in range(5)]

    def get_evidence(self, pid, since=None, limit=200):
        return [{"ts_start": "2026-11-08T10:02:00+00:00", "modality": "vitals",
                 "type": "news2_high", "score": 0.9, "severity": "critical",
                 "explanation": "NEWS2 = 8"}]

    def get_risk(self, pid, since=None):
        return [{"ts": "2026-11-08T10:02:00+00:00", "risk_score": 82.4}]

    def list_media(self, pid=None):
        return [{"media_id": "m1", "kind": "audio", "status": "done", "original_name": "c.wav",
                 "recorded_at": "2026-11-08T10:00:00+00:00", "artifacts": {}}]

    def get_media(self, mid):
        return {"media_id": mid, "status": "done", "artifacts": {}, "transcript": {
            "segments": [{"speaker": "Guest-2", "text": "Estou com falta de ar", "offset_s": 4}],
            "analysis": {"sentiments": [{"sentiment": "negative"}],
                         "terms": [{"term": "falta de ar", "category": "respiratorio",
                                    "segment_index": 0}]}}}

    def patient_report(self, pid):
        return {"report_html": f"reports/{pid}/r.html", "report_pdf": f"reports/{pid}/r.pdf"}

    def get_file(self, key):
        return b"%PDF-1.7" if key.endswith(".pdf") else b"<html></html>"


@pytest.fixture()
def app_test(monkeypatch):
    st_testing = pytest.importorskip("streamlit.testing.v1")
    import streamlit as st

    monkeypatch.setattr(api_client, "ApiClient", FakeApi)
    FakeApi.acks = []
    st.cache_resource.clear()
    st.cache_data.clear()
    yield lambda: st_testing.AppTest.from_file(str(APP), default_timeout=30)
    st.cache_resource.clear()


def test_overview_lists_patients_and_acks_alert(app_test):
    at = app_test().run()
    assert not at.exception
    assert at.title[0].value == "Painel geral"
    md = " ".join(m.value for m in at.markdown)
    assert "Bruno" in md and "Risco crítico" in md
    assert md.index("Bruno") < md.index("Ana")  # ordenado pelo risco
    at.button(key=f"confirm-{ALERT['alert_id']}").click().run()
    assert not at.exception
    assert FakeApi.acks == [(ALERT["alert_id"], "confirmed", "medico.demo", "")]


@pytest.mark.parametrize("page", ["Paciente", "Enviar mídia", "Sobre"])
def test_other_pages_render(app_test, page):
    if page == "Paciente":
        try:  # st.dataframe precisa do pyarrow (quebrado na .venv: pyarrow 26 x numpy<2, ver T07)
            import pyarrow  # noqa: F401
        except ImportError:
            pytest.skip("pyarrow não importa nesta .venv")
    at = app_test()
    at.query_params["patient"] = "P-0002"
    at.run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
    assert at.title[0].value in (page, "Sobre o MedWatch")
