"""Checagem prévia da gravação da demonstração (T38).

Imprime ✓ ou ✗ para cada item e termina com código 1 se faltar algo crítico. Em modo falso
(USE_FAKE_AZURE=true) lista exatamente o que depende do humano. Não imprime chaves.

Uso: python scripts/preflight_demo.py [--api URL] [--send-test]
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import redis

from medwatch.config import Settings, get_settings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# stream → consumer group; nomes copiados das constantes dos workers (mantidos por teste)
STREAM_GROUPS = {"vitals": "worker-anomaly", "jobs.video": "worker-video",
                 "jobs.audio": "worker-audio", "jobs.text": "worker-text",
                 "evidence": "worker-fusion", "alerts": "worker-alerts"}
MAX_IDLE_MS = 60_000
REQUIRED_SAMPLES = ["physio_squat_correct.mp4", "physio_squat_wrong.mp4", "bed_fall.mp4",
                    "consulta_p0001.wav", "laudo_p0002.txt", "hello_ptbr.wav"]
REQUIRED_MODELS = ["vitals_iforest.joblib", "vitals_iforest.json", "yolov8n-pose.pt"]


@dataclass
class Result:
    ok: bool
    name: str
    detail: str = ""
    critical: bool = True
    human: bool = False     # só o humano resolve (chaves, webhooks, gravações)


def check_api(client: httpx.Client) -> Result:
    try:
        ok = client.get("/health").status_code == 200
    except httpx.HTTPError as exc:
        return Result(False, "API (/health)", type(exc).__name__)
    return Result(ok, "API (/health)", "" if ok else "resposta não OK")


def check_workers(r: redis.Redis, groups: dict[str, str] = STREAM_GROUPS) -> list[Result]:
    """Cada grupo precisa ter um consumidor com `idle` baixo (worker de pé e lendo)."""
    out = []
    for group in sorted(set(groups.values())):
        stream = next(s for s, g in groups.items() if g == group)
        try:
            consumers = r.xinfo_consumers(stream, group)
        except redis.ResponseError:
            out.append(Result(False, f"{group}", f"grupo ausente em {stream}"))
            continue
        idle = min((c["idle"] for c in consumers), default=None)
        ok = idle is not None and idle <= MAX_IDLE_MS
        out.append(Result(ok, f"{group}",
                          "sem consumidor" if idle is None else f"idle {idle / 1000:.0f} s"))
    return out


def check_azure(s: Settings, real_call: Callable[[], None] | None = None) -> list[Result]:
    if s.use_fake_azure:
        return [Result(False, "Azure real (USE_FAKE_AZURE=false)",
                       "USE_FAKE_AZURE=true: provisionar a Azure e preencher o .env", human=True)]
    keys = {"AZURE_SPEECH_KEY": s.azure_speech_key, "AZURE_LANGUAGE_KEY": s.azure_language_key,
            "AZURE_LANGUAGE_ENDPOINT": s.azure_language_endpoint}
    missing = [k for k, v in keys.items() if not v]
    out = [Result(not missing, "chaves Azure", "faltam: " + ", ".join(missing) if missing else "",
                  human=bool(missing))]
    if real_call and not missing:
        try:
            real_call()
            out.append(Result(True, "chamada real à Azure"))
        except Exception as exc:  # noqa: BLE001
            out.append(Result(False, "chamada real à Azure", type(exc).__name__))
    return out


def check_alert_channels(s: Settings, send_test: bool = False,
                         transport: httpx.BaseTransport | None = None) -> list[Result]:
    out = [Result(bool(s.teams_webhook_url), "TEAMS_WEBHOOK_URL", human=True),
           Result(bool(s.logic_app_email_url and s.alert_email_to),
                  "LOGIC_APP_EMAIL_URL e ALERT_EMAIL_TO", human=True)]
    if send_test:
        from medwatch.alerts.channels import EmailChannel, TeamsChannel
        from medwatch.contracts import Alert
        now = datetime.now(UTC)
        alert = Alert(patient_id="T-PREFLIGHT", level="info", risk_score=0,
                      title="Teste do MedWatch (preflight)",
                      summary="Mensagem de teste da checagem prévia.\nPode ignorar.",
                      evidence_ids=[], created_at=now, updated_at=now)
        channels = []
        if s.teams_webhook_url:
            channels.append(TeamsChannel(s.teams_webhook_url, s.dashboard_url, transport))
        if s.logic_app_email_url and s.alert_email_to:
            channels.append(EmailChannel(s.logic_app_email_url, s.alert_email_to, transport))
        for ch in channels:
            try:
                ch.send(alert)
                out.append(Result(True, f"envio de teste ({ch.name})"))
            except Exception as exc:  # noqa: BLE001
                out.append(Result(False, f"envio de teste ({ch.name})", type(exc).__name__))
    return out


def check_files(samples: Path, models: Path) -> list[Result]:
    missing_s = [f for f in REQUIRED_SAMPLES if not (samples / f).exists()]
    missing_m = [f for f in REQUIRED_MODELS if not (models / f).exists()]
    return [Result(not missing_s, "amostras de data/samples/",
                   "faltam: " + ", ".join(missing_s) if missing_s else "", human=bool(missing_s)),
            Result(not missing_m, "modelos em models/",
                   "faltam: " + ", ".join(missing_m) if missing_m else "")]


def check_clean_db(client: httpx.Client) -> Result:
    """Banco limpo: nenhum alerta, nenhuma evidência e nenhum paciente `T-` (testes)."""
    try:
        patients = client.get("/patients").json()
        alerts = client.get("/alerts").json()
        evidence = sum(len(client.get(f"/patients/{p['patient_id']}/evidence").json())
                       for p in patients)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return Result(False, "banco limpo", type(exc).__name__)
    test_rows = [p["patient_id"] for p in patients if p["patient_id"].startswith("T-")]
    problems = []
    if alerts:
        problems.append(f"{len(alerts)} alertas")
    if evidence:
        problems.append(f"{evidence} evidências")
    if test_rows:
        problems.append(f"pacientes de teste {', '.join(test_rows)}")
    return Result(not problems, "banco limpo",
                  "; ".join(problems) + (" (rode docker compose down -v)" if problems else ""))


def azure_real_call() -> None:
    import check_azure
    check_azure.check_language()


def report(results: list[Result]) -> int:
    for x in results:
        mark = "✓" if x.ok else "✗"
        tag = "" if x.ok else (" [HUMANO]" if x.human else "")
        print(f"{mark} {x.name}{tag}" + (f" — {x.detail}" if x.detail else ""))
    failed = [x for x in results if not x.ok and x.critical]
    human = [x.name for x in failed if x.human]
    print(f"\n{len(results) - len(failed)}/{len(results)} itens ok.")
    if human:
        print("Dependem do humano: " + "; ".join(human))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=s.api_base_url)
    ap.add_argument("--send-test", action="store_true",
                    help="envia uma mensagem de teste ao Teams e ao e-mail")
    a = ap.parse_args(argv)
    client = httpx.Client(base_url=a.api, timeout=15)
    r = redis.Redis.from_url(s.redis_url, decode_responses=True)
    results = [check_api(client)]
    try:
        results += check_workers(r)
    except redis.RedisError as exc:
        results.append(Result(False, "Redis", type(exc).__name__))
    results += check_azure(s, azure_real_call)
    results += check_alert_channels(s, a.send_test)
    results += check_files(ROOT / "data" / "samples", ROOT / "models")
    if results[0].ok:
        results.append(check_clean_db(client))
    return report(results)


if __name__ == "__main__":
    sys.exit(main())
