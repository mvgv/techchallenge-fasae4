"""Replay acelerado dos eventos simulados para os streams (python -m medwatch.simulator.replay)."""
import argparse
import json
import logging
import time
from datetime import datetime, timedelta

from medwatch.bus import Bus
from medwatch.config import get_settings
from medwatch.simulator.synthetic import demo_timeline, generate_patient_timeline
from medwatch.timeutil import parse_ts, utcnow

log = logging.getLogger(__name__)

DEMO_PATIENTS = [f"P-{i:04d}" for i in range(1, 6)]
DEMO_PHASES = [(0, 60.0), (360, 6.0)]
STREAMS = {"VitalObservation": "vitals", "PrescriptionEvent": "prescriptions",
           "MovementSample": "movement"}


def default_start(scenario: str, now: datetime | None = None) -> datetime:
    """Início do tempo simulado: demo = dia anterior 19:00 UTC; outros = agora - 24h."""
    now = now or utcnow()
    if scenario == "demo":
        return (now - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
    return (now - timedelta(hours=24)).replace(second=0, microsecond=0)


def build_events(scenario: str, n_patients: int, start: datetime, seed: int = 0,
                 mimic_split: str | None = None, mimic_hours: float | None = None):
    """Retorna (eventos [(ts, stream, modelo)], rótulos) já ordenados por ts.

    No cenário `mimic` com `mimic_split`, usa todos os pacientes da divisão, com a
    primeira observação de cada um deslocada para `start`.
    """
    events: list[tuple[datetime, str, object]] = []
    labels: list[dict] = []
    if scenario == "demo":
        timelines = [demo_timeline(p, start, seed + i) for i, p in enumerate(DEMO_PATIENTS)]
    elif scenario == "mimic":
        from medwatch.simulator.mimic import load_mimic
        if mimic_split:
            vitals, rx = load_mimic(None, split=mimic_split, rebase_start=start,
                                    window_hours=mimic_hours)
        else:
            vitals, rx = load_mimic(n_patients, window_hours=mimic_hours)
        for v in vitals:
            events.append((v.ts, "vitals", v))
        for e in rx:
            events.append((e.ts, "prescriptions", e))
        timelines = []
    else:
        timelines = [generate_patient_timeline(f"P-{i + 1:04d}", start, 24 * 60, scenario,
                                               seed + i) for i in range(n_patients)]
    for vitals, rx, moves, lab in timelines:
        events += [(o.ts, "vitals", o) for o in vitals]
        events += [(e.ts, "prescriptions", e) for e in rx]
        events += [(m.ts, "movement", m) for m in moves]
        labels += lab
    events.sort(key=lambda x: x[0])
    return events, labels


def speedup_at(phases: list[tuple[int, float]], sim_minute: float) -> float:
    cur = phases[0][1]
    for m, s in phases:
        if sim_minute >= m:
            cur = s
    return cur


def run(scenario: str, n_patients: int, speedup: float, start: datetime, fast: bool = False,
        bus: Bus | None = None, sleep=time.sleep, seed: int = 0,
        mimic_split: str | None = None, mimic_hours: float | None = None) -> int:
    """Publica os eventos; retorna quantas mensagens foram publicadas."""
    bus = bus or Bus()
    events, labels = build_events(scenario, n_patients, start, seed, mimic_split, mimic_hours)
    gt_dir = get_settings().local_storage_dir / "ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)
    (gt_dir / f"{scenario}.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    phases = DEMO_PHASES if scenario == "demo" else [(0, speedup)]
    prev: datetime | None = None
    count = 0
    i = 0
    while i < len(events):
        ts = events[i][0]
        if prev is not None and not fast:
            minute = (prev - start).total_seconds() / 60
            sleep((ts - prev).total_seconds() / speedup_at(phases, minute))
        while i < len(events) and events[i][0] == ts:
            _, stream, model = events[i]
            bus.publish(stream, model)
            count += 1
            i += 1
        bus.r.set("sim:clock", ts.isoformat())
        prev = ts
    log.info("Replay %s concluído: %d mensagens", scenario, count)
    return count


def main() -> None:
    st = get_settings()
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="início do tempo simulado (ISO 8601)")
    ap.add_argument("--fast", action="store_true", help="publica sem espera")
    ap.add_argument("--mimic-split", help="replay do MIMIC só com esta divisão de "
                    "config/splits.yaml (calibracao, validacao, reservado); implica cenário mimic")
    ap.add_argument("--mimic-hours", type=float, default=None,
                    help="MIMIC: só as primeiras N horas de cada paciente")
    args = ap.parse_args()
    logging.basicConfig(level=st.log_level)
    scenario = "mimic" if args.mimic_split else st.sim_scenario
    if scenario == "demo":
        from medwatch import db
        for i, pid in enumerate(DEMO_PATIENTS, 1):
            db.upsert_patient(pid, f"Paciente {i:02d}", f"UTI-{i:02d}")
    start = parse_ts(args.start) if args.start else default_start(scenario)
    if scenario == "mimic" and args.mimic_split:
        from medwatch import db
        from medwatch.simulator.mimic import split_patients
        for pid in split_patients(args.mimic_split):
            db.upsert_patient(pid, f"MIMIC {pid[2:]}", f"MIMIC-{args.mimic_split}")
    run(scenario, st.sim_patients, st.sim_speedup, start, fast=args.fast,
        mimic_split=args.mimic_split, mimic_hours=args.mimic_hours)


if __name__ == "__main__":
    main()
