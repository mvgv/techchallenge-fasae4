"""Roteiro automatizado da demonstração (seção 7 do plano).

Uso: `python scripts/run_demo.py` com a API, o banco, o Redis e os workers no ar.

1. Verifica `GET /health`.
2. Cria os pacientes P-0001..P-0005 (mesmos dados de `scripts/seed.py`, via `POST /patients`).
3. Inicia o simulador com `SIM_SCENARIO=demo` como subprocesso (ou, com `--external-simulator`,
   pede para rodar `docker compose --profile demo up simulator`).
4. Lê `sim:clock` no Redis a cada segundo e, nos minutos simulados da tabela 7.1, envia as
   amostras de `data/samples/` com `recorded_at = sim:clock`.
5. Imprime cada etapa com o horário real e o simulado, para guiar a gravação do vídeo.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx
import redis

from medwatch.config import get_settings
from medwatch.simulator.replay import DEMO_PATIENTS, default_start
from medwatch.timeutil import parse_ts

ROOT = Path(__file__).resolve().parents[1]
END_MINUTE = 479  # último minuto publicado pelo cenário demo (0–479)


@dataclass(frozen=True)
class DemoStep:
    """Uma mídia enviada pela demo num minuto simulado."""

    minute: int
    patient_id: str
    filename: str
    kind: str  # video | audio | document
    description: str
    mode: str | None = None
    exercise: str | None = None


DEMO_STEPS: list[DemoStep] = [
    DemoStep(365, "P-0003", "physio_squat_wrong.mp4", "video",
             "fisioterapia (agachamento incorreto)", mode="physio", exercise="squat"),
    DemoStep(370, "P-0001", "consulta_p0001.wav", "audio", "áudio da consulta encenada"),
    DemoStep(385, "P-0002", "laudo_p0002.txt", "document", "laudo em texto"),
    DemoStep(410, "P-0004", "bed_fall.mp4", "video", "queda do leito", mode="bed"),
]

# Opcional (T40, --keraal): clipe de voluntário saudável reservado do Keraal; no vídeo de entrega
# ele substitui o do agachamento (o limite de 15 minutos não comporta os dois).
KERAAL_STEP = DemoStep(375, "P-0003", "physio_keraal_wrong.mp4", "video",
                       "fisioterapia (esconder o rosto, Keraal, voluntário saudável reservado)",
                       mode="physio", exercise="hide_face")


def log(msg: str, clock: datetime | None = None, start: datetime | None = None) -> None:
    """Imprime uma linha com horário real e, se houver, o tempo simulado."""
    wall = datetime.now().strftime("%H:%M:%S")
    sim = ""
    if clock is not None and start is not None:
        sim = f" [sim min {sim_minute(clock, start):5.1f} | {clock:%H:%M} UTC]"
    print(f"[{wall}]{sim} {msg}", flush=True)


def sim_minute(clock: datetime, start: datetime) -> float:
    """Minuto simulado desde o início do cenário."""
    return (clock - start).total_seconds() / 60


def read_clock(r: redis.Redis) -> datetime | None:
    """Lê `sim:clock`; None se o simulador ainda não publicou."""
    raw = r.get("sim:clock")
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    return parse_ts(raw)


def check_health(client: httpx.Client) -> bool:
    """True se `GET /health` responde 200."""
    try:
        return client.get("/health").status_code == 200
    except httpx.HTTPError:
        return False


def seed_patients(client: httpx.Client) -> None:
    """Cria (ou atualiza) os pacientes da demo, com os mesmos dados de `scripts/seed.py`."""
    for i, pid in enumerate(DEMO_PATIENTS, 1):
        resp = client.post("/patients", json={"patient_id": pid,
                                              "display_name": f"Paciente {i:02d}",
                                              "bed": f"UTI-{i:02d}"})
        resp.raise_for_status()


def missing_samples(samples_dir: Path, steps: list[DemoStep] = DEMO_STEPS) -> list[str]:
    """Nomes das amostras da demo que não existem em `samples_dir`."""
    return [s.filename for s in steps if not (samples_dir / s.filename).is_file()]


def send_step(client: httpx.Client, step: DemoStep, samples_dir: Path,
              recorded_at: datetime) -> dict:
    """Envia a mídia do passo pela API com `recorded_at` = tempo simulado."""
    path = samples_dir / step.filename
    if step.kind == "document":
        resp = client.post("/documents", json={
            "patient_id": step.patient_id, "text": path.read_text(encoding="utf-8"),
            "recorded_at": recorded_at.isoformat(), "title": path.stem})
    else:
        data = {"patient_id": step.patient_id, "kind": step.kind,
                "recorded_at": recorded_at.isoformat()}
        if step.mode:
            data["mode"] = step.mode
        if step.exercise:
            data["exercise"] = step.exercise
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fh:
            resp = client.post("/media", data=data, files={"file": (path.name, fh, mime)},
                               timeout=120)
    resp.raise_for_status()
    return resp.json()


def start_simulator(start: datetime, fast_until: float | None = None,
                    tail_speedup: float | None = None) -> subprocess.Popen:
    """Inicia `medwatch.simulator.replay` com `SIM_SCENARIO=demo` e o início informado."""
    env = {**os.environ, "SIM_SCENARIO": "demo"}
    cmd = [sys.executable, "-m", "medwatch.simulator.replay", "--start", start.isoformat()]
    if fast_until is not None:
        cmd += ["--fast-until", str(fast_until)]
    if tail_speedup is not None:
        cmd += ["--tail-speedup", str(tail_speedup)]
    return subprocess.Popen(cmd, env=env, cwd=ROOT)


def run_demo(client: httpx.Client, r: redis.Redis, start: datetime, samples_dir: Path,
             steps: list[DemoStep] = DEMO_STEPS, proc: subprocess.Popen | None = None,
             sleep: Callable[[float], None] = time.sleep, poll: float = 1.0,
             end_minute: int = END_MINUTE) -> dict[str, list[str]]:
    """Acompanha `sim:clock` e envia cada mídia no minuto certo; devolve o que foi feito."""
    pending = sorted(steps, key=lambda s: s.minute)
    result: dict[str, list[str]] = {"sent": [], "skipped": [], "failed": []}
    announced = set()
    last_clock: datetime | None = None
    while True:
        clock = read_clock(r)
        if clock is not None and clock != last_clock:
            last_clock = clock
            minute = sim_minute(clock, start)
            for mark in (0, 360, end_minute):
                if minute >= mark and mark not in announced:
                    announced.add(mark)
                    text = {0: "simulador publicando (histórico a 60x)",
                            360: "início da janela da demo (6x)",
                            end_minute: "fim do cenário demo"}[mark]
                    log(text, clock, start)
            while pending and minute >= pending[0].minute:
                step = pending.pop(0)
                _do_step(client, step, samples_dir, clock, start, result)
            if not pending and minute >= end_minute:
                break
        if proc is not None and proc.poll() is not None:
            for step in pending:
                log(f"simulador terminou antes do minuto {step.minute}: {step.filename} "
                    "não enviado", last_clock, start)
                result["skipped"].append(step.filename)
            break
        sleep(poll)
    return result


def _do_step(client: httpx.Client, step: DemoStep, samples_dir: Path, clock: datetime,
             start: datetime, result: dict[str, list[str]]) -> None:
    if not (samples_dir / step.filename).is_file():
        log(f"{step.patient_id}: amostra {step.filename} ausente, etapa pulada "
            "(ver data/samples/README.md)", clock, start)
        result["skipped"].append(step.filename)
        return
    try:
        res = send_step(client, step, samples_dir, clock)
    except (httpx.HTTPError, OSError) as e:
        log(f"{step.patient_id}: falha ao enviar {step.filename}: {e}", clock, start)
        result["failed"].append(step.filename)
        return
    log(f"{step.patient_id}: enviado {step.description} ({step.filename}), "
        f"media_id={res.get('media_id')}", clock, start)
    result["sent"].append(step.filename)


def print_alerts(client: httpx.Client) -> None:
    """Lista os alertas gerados (para conferir o resultado esperado da tabela 7.1)."""
    try:
        alerts = client.get("/alerts").json()
    except (httpx.HTTPError, ValueError) as e:
        log(f"não foi possível listar os alertas: {e}")
        return
    log(f"{len(alerts)} alerta(s) no sistema:")
    for a in alerts:
        print(f"    {a.get('patient_id')} [{a.get('level')}] {a.get('title')} "
              f"(risco {a.get('risk_score')}, {a.get('status')})", flush=True)


def main() -> int:
    """Executa a demonstração completa."""
    st = get_settings()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default=st.api_base_url, help="URL base da API")
    ap.add_argument("--samples", type=Path, default=ROOT / "data" / "samples")
    ap.add_argument("--start", help="início do tempo simulado (ISO 8601); padrão: o do replay")
    ap.add_argument("--external-simulator", action="store_true",
                    help="não inicia o simulador; use docker compose --profile demo up simulator")
    ap.add_argument("--fast-until", type=float, default=None, metavar="MIN",
                    help="simulador: sem espera até este minuto simulado (ex.: 355)")
    ap.add_argument("--tail-speedup", type=float, default=None, metavar="FATOR",
                    help="simulador: velocidade da fase final (ex.: 12 → minutos 360–480 em ~10 min)")
    ap.add_argument("--keraal", action="store_true",
                    help="acrescenta o clipe do Keraal (minuto 375, P-0003)")
    args = ap.parse_args()
    steps = DEMO_STEPS + [KERAAL_STEP] if args.keraal else DEMO_STEPS

    client = httpx.Client(base_url=args.api, timeout=30)
    r = redis.Redis.from_url(st.redis_url, decode_responses=True)
    start = parse_ts(args.start) if args.start else default_start("demo")

    log(f"1/5 verificando {args.api}/health")
    if not check_health(client):
        log("API indisponível: suba o ambiente (seção 9.7 do plano) e tente de novo")
        return 1
    log("2/5 criando pacientes P-0001..P-0005")
    seed_patients(client)
    missing = missing_samples(args.samples, steps)
    if missing:
        log(f"aviso: amostras ausentes em {args.samples}: {', '.join(missing)} "
            "(essas etapas serão puladas)")

    r.delete("sim:clock")
    proc = None
    if args.external_simulator:
        log("3/5 rode agora: docker compose --profile demo up simulator "
            f"(início simulado esperado: {start.isoformat()})")
    else:
        log(f"3/5 iniciando o simulador (SIM_SCENARIO=demo, início {start.isoformat()})")
        proc = start_simulator(start, args.fast_until, args.tail_speedup)
    log("4/5 acompanhando sim:clock; mídias serão enviadas nos minutos "
        + ", ".join(f"{s.minute} ({s.patient_id})" for s in steps))
    try:
        result = run_demo(client, r, start, args.samples, steps=steps, proc=proc)
    except KeyboardInterrupt:
        log("interrompido pelo usuário")
        if proc is not None:
            proc.terminate()
        return 130
    if proc is not None:
        proc.wait()
    log(f"5/5 fim: enviados {result['sent']}, pulados {result['skipped']}, "
        f"falhas {result['failed']}")
    sleep_s = 5
    log(f"aguardando {sleep_s} s para os workers processarem a última mídia")
    time.sleep(sleep_s)
    print_alerts(client)
    return 0 if not result["failed"] else 2


if __name__ == "__main__":
    sys.exit(main())

