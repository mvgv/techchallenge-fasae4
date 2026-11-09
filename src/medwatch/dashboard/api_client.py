"""Cliente HTTP fino da API do MedWatch usado pelo dashboard.

Todas as chamadas são feitas pelo servidor do Streamlit: `API_BASE_URL`
(ex.: `http://api:8000`) só resolve dentro da rede do Docker, então arquivos
são baixados aqui e entregues ao navegador como bytes.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from medwatch.config import get_settings

TIMEOUT_S = 10.0
UPLOAD_TIMEOUT_S = 120.0


def _show_error(message: str) -> None:
    """Exibe o erro no Streamlit (ou ignora fora dele)."""
    try:
        import streamlit as st

        st.error(message)
    except Exception:  # noqa: BLE001 - fora do Streamlit não há onde exibir
        pass


def _detail(resp: httpx.Response) -> str:
    """Extrai a mensagem de erro da resposta da API."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300] or resp.reason_phrase
    detail = body.get("detail", body) if isinstance(body, dict) else body
    if isinstance(detail, list):  # erros de validação do FastAPI
        return "; ".join(str(d.get("msg", d)) if isinstance(d, dict) else str(d) for d in detail)
    return str(detail)


class ApiClient:
    """Funções finas sobre httpx para as rotas da seção 3.6 do plano."""

    def __init__(self, base_url: str | None = None,
                 transport: httpx.BaseTransport | None = None,
                 on_error=_show_error) -> None:
        self.base_url = (base_url or get_settings().api_base_url).rstrip("/")
        self.transport = transport
        self.on_error = on_error

    def _request(self, method: str, path: str, *, timeout: float = TIMEOUT_S,
                 raw: bool = False, **kwargs: Any) -> Any:
        """Faz a requisição; em erro chama `on_error` e devolve None."""
        try:
            with httpx.Client(base_url=self.base_url, timeout=timeout,
                              transport=self.transport) as client:
                resp = client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            self.on_error(f"Falha ao acessar a API ({method} {path}): {exc}")
            return None
        if resp.status_code >= 400:
            self.on_error(f"API respondeu {resp.status_code} em {method} {path}: {_detail(resp)}")
            return None
        if raw:
            return resp.content
        return resp.json() if resp.content else {}

    # --- saúde e pacientes ---
    def health(self) -> dict | None:
        """GET /health."""
        return self._request("GET", "/health")

    def list_patients(self) -> list[dict] | None:
        """GET /patients."""
        return self._request("GET", "/patients")

    def get_patient(self, patient_id: str) -> dict | None:
        """GET /patients/{id}."""
        return self._request("GET", f"/patients/{quote(patient_id)}")

    def get_vitals(self, patient_id: str, since: str | None = None,
                   until: str | None = None) -> list[dict] | None:
        """GET /patients/{id}/vitals."""
        params = {k: v for k, v in {"since": since, "until": until}.items() if v}
        return self._request("GET", f"/patients/{quote(patient_id)}/vitals", params=params)

    def get_evidence(self, patient_id: str, since: str | None = None,
                     limit: int = 200) -> list[dict] | None:
        """GET /patients/{id}/evidence."""
        params: dict[str, Any] = {"limit": limit}
        if since:
            params["since"] = since
        return self._request("GET", f"/patients/{quote(patient_id)}/evidence", params=params)

    def get_risk(self, patient_id: str, since: str | None = None) -> list[dict] | None:
        """GET /patients/{id}/risk."""
        params = {"since": since} if since else {}
        return self._request("GET", f"/patients/{quote(patient_id)}/risk", params=params)

    # --- alertas ---
    def list_alerts(self, status: str | None = None,
                    patient_id: str | None = None) -> list[dict] | None:
        """GET /alerts."""
        params = {k: v for k, v in {"status": status, "patient_id": patient_id}.items() if v}
        return self._request("GET", "/alerts", params=params)

    def ack_alert(self, alert_id: str, decision: str, user: str = "medico.demo",
                  note: str | None = None) -> dict | None:
        """POST /alerts/{id}/ack com decision confirmed|dismissed."""
        body = {"user": user, "decision": decision, "note": note or None}
        return self._request("POST", f"/alerts/{alert_id}/ack", json=body)

    # --- mídia e arquivos ---
    def list_media(self, patient_id: str | None = None) -> list[dict] | None:
        """GET /media."""
        params = {"patient_id": patient_id} if patient_id else {}
        return self._request("GET", "/media", params=params)

    def get_media(self, media_id: str) -> dict | None:
        """GET /media/{id}."""
        return self._request("GET", f"/media/{media_id}")

    def upload_media(self, *, filename: str, content: bytes, patient_id: str, kind: str,
                     mode: str | None = None, exercise: str | None = None,
                     camera: str | None = None, patient_speaker: str | None = None,
                     recorded_at: str | None = None) -> dict | None:
        """POST /media (multipart)."""
        fields = {"patient_id": patient_id, "kind": kind, "mode": mode, "exercise": exercise,
                  "camera": camera, "patient_speaker": patient_speaker,
                  "recorded_at": recorded_at}
        data = {k: v for k, v in fields.items() if v}
        return self._request("POST", "/media", data=data, files={"file": (filename, content)},
                             timeout=UPLOAD_TIMEOUT_S)

    def get_file(self, key: str) -> bytes | None:
        """GET /files/{key}: baixa o arquivo do storage como bytes."""
        return self._request("GET", f"/files/{quote(key)}", raw=True, timeout=UPLOAD_TIMEOUT_S)

    # --- relatórios ---
    def patient_report(self, patient_id: str) -> dict | None:
        """POST /reports/patient/{id}: devolve as chaves do HTML e do PDF."""
        return self._request("POST", f"/reports/patient/{quote(patient_id)}",
                             timeout=UPLOAD_TIMEOUT_S)
