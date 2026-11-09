from datetime import UTC, datetime

from medwatch.reports.render import (
    DISCLAIMER,
    build_patient_report,
    build_session_report,
    html_to_pdf,
    render_html,
)
from medwatch.storage import LocalStorage

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

FINDINGS = {
    "analysis_fps": 5.0, "video": {"duration": 10.0},
    "reps": [(0, 20), (20, 40)],
    "series": {"knee": [170.0 - (i % 20) * 4 for i in range(50)]},
    "findings": [{"type": "physio_low_rom", "t_start": 2.0, "t_end": 4.0,
                  "explanation": "Amplitude reduzida <b>"}],
}
MEDIA = {"media_id": "m1", "patient_id": "P-0003", "patient_name": "Maria Teste",
         "mode": "physio", "exercise": "squat", "recorded_at": T0}


def test_video_template_has_patient_and_disclaimer():
    html = render_html("video_report.html.j2", {
        "media": MEDIA, "findings": FINDINGS, "recorded_at": "x", "duration": 10.0,
        "n_reps": 2, "by_type": {"physio_low_rom": 1}, "frames": [], "chart": None})
    assert "Maria Teste" in html and DISCLAIMER in html
    assert "&lt;b&gt;" in html  # autoescape


def test_patient_template():
    patient = {"patient_id": "P-1", "display_name": "João Teste", "bed": "L1"}
    vitals = [{"ts": T0, "hr": 80, "spo2": 97, "rr": 16}]
    ev = [{"modality": "vitals", "type": "news2_high", "score": 0.8, "ts_start": T0,
           "explanation": "NEWS2 alto"}]
    html = build_patient_report(patient, {"risk_score": 55.0, "level": "warning"}, [], ev, vitals)
    assert "João Teste" in html and DISCLAIMER in html and "data:image/png;base64," in html


def test_build_session_report_saves_artifacts(tmp_path):
    st = LocalStorage(tmp_path)
    out = build_session_report(MEDIA, FINDINGS, st)
    assert out["report_html"] == "artifacts/m1/report.html"
    assert b"Maria Teste" in b"".join(st.open_stream(out["report_html"]))
    if "report_pdf" in out:
        assert b"".join(st.open_stream(out["report_pdf"])).startswith(b"%PDF")


def test_html_to_pdf():
    pdf = html_to_pdf("<p>oi</p>")
    assert pdf is None or pdf.startswith(b"%PDF")


def test_patient_report_route(tmp_path):
    from uuid import uuid4

    import pytest
    from fastapi.testclient import TestClient

    from medwatch import db
    from medwatch.api.deps import get_storage_dep
    from medwatch.api.main import app

    if not db.ping():
        pytest.skip("banco indisponível")
    pid = f"T-{uuid4().hex[:8]}"
    db.upsert_patient(pid, "Rota Teste", "L2")
    st = LocalStorage(tmp_path)
    app.dependency_overrides[get_storage_dep] = lambda: st
    try:
        c = TestClient(app)
        r = c.post(f"/reports/patient/{pid}")
        assert r.status_code == 200
        assert b"Rota Teste" in b"".join(st.open_stream(r.json()["report_html"]))
        assert c.post("/reports/patient/NAO-EXISTE").status_code == 404
    finally:
        app.dependency_overrides.pop(get_storage_dep, None)
