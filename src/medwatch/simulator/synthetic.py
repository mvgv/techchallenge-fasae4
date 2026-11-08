"""Gerador sintético determinístico de séries de vitais, prescrições e movimento."""
from datetime import datetime, timedelta

import numpy as np

from medwatch.contracts import MovementSample, PrescriptionEvent, VitalObservation

SCENARIOS = ("normal", "respiratory_deterioration", "hypotension", "tachy_spike",
             "sensor_artifact", "night_agitation", "inactivity", "rx_risky", "demo")

_NOISE_SD = {"hr": 2.0, "sbp": 3.0, "dbp": 2.0, "spo2": 0.4, "rr": 0.8, "temp": 0.05}
_DEFAULT_ONSET = {"respiratory_deterioration": 600, "hypotension": 600, "tachy_spike": 600,
                  "sensor_artifact": 600, "night_agitation": None, "inactivity": 600,
                  "rx_risky": 60}


def _label(pid: str, typ: str, start: datetime, a: int, b: int) -> dict:
    return {"patient_id": pid, "type": typ,
            "ts_start": (start + timedelta(minutes=a)).isoformat(),
            "ts_end": (start + timedelta(minutes=b)).isoformat()}


def _ramp(arr: np.ndarray, onset: int, dur: int, v0: float, v1: float) -> None:
    """Rampa linear de v0 a v1 em dur minutos; depois mantém v1 até o fim."""
    for i in range(onset, len(arr)):
        frac = min((i - onset) / dur, 1.0)
        arr[i] = v0 + (v1 - v0) * frac


def _minutes_to_next_hour(start: datetime, hour: int) -> int:
    m = 0
    while (start + timedelta(minutes=m)).hour != hour:
        m += 1
    return m


def build_timeline(patient_id: str, start: datetime, minutes: int, seed: int,
                   events: list[dict],
                   extra_rx: list[tuple[int, str, float | None, str]] | None = None):
    """Constrói a linha do tempo aplicando uma lista de eventos (dict com `scenario`, `onset`...)."""
    rng = np.random.default_rng(seed)
    base = {"hr": rng.normal(75, 8), "sbp": rng.normal(120, 10), "dbp": rng.normal(75, 7),
            # limitado a [96, 100]: garante que o cenário normal fique em spo2 >= 94
            "spo2": float(np.clip(rng.normal(97.5, 0.8), 96.0, 100.0)),
            "rr": rng.normal(15, 2), "temp": rng.normal(36.7, 0.3)}
    series: dict[str, np.ndarray] = {}
    for k, b in base.items():
        x = np.empty(minutes)
        prev = b
        for t in range(minutes):
            prev = b + 0.8 * (prev - b) + rng.normal(0, _NOISE_SD[k])
            x[t] = prev
        series[k] = x
    series["spo2"] = np.minimum(series["spo2"], 100.0)

    ts = [start + timedelta(minutes=i) for i in range(minutes)]
    hours = np.array([t.hour for t in ts])
    day = (hours >= 7) & (hours < 22)
    activity = np.clip(np.where(day, rng.normal(30, 10, minutes), rng.normal(5, 3, minutes)),
                       0, 100)
    in_bed = np.ones(minutes, dtype=bool)
    in_bed[day & (rng.random(minutes) < 0.1)] = False
    on_oxygen = np.zeros(minutes, dtype=bool)

    pid = patient_id
    rx: list[PrescriptionEvent] = []
    labels: list[dict] = []

    def add_rx(minute: int, drug: str, dose: float | None, unit: str, action: str,
               route: str = "IV") -> None:
        if 0 <= minute < minutes:
            rx.append(PrescriptionEvent(rx_id=f"{pid}-rx{len(rx) + 1}", patient_id=pid,
                                        ts=start + timedelta(minutes=minute), drug=drug,
                                        dose=dose, unit=unit, route=route, action=action))

    for drug, dose in [("dipirona", 1000), ("omeprazol", 40),
                       ("ceftriaxona", 1000)][: 2 + int(rng.integers(0, 2))]:
        add_rx(0, drug, dose, "mg", "start")
    for minute, drug, dose, action in extra_rx or []:
        add_rx(minute, drug, dose, "mg", action)

    for ev in events:
        sc = ev["scenario"]
        if sc == "normal":
            continue
        onset = ev.get("onset")
        if onset is None:
            onset = _DEFAULT_ONSET.get(sc)
        if sc == "night_agitation" and onset is None:
            onset = _minutes_to_next_hour(start, 1)
        if onset is None or onset >= minutes:
            continue
        if sc == "respiratory_deterioration":
            d = ev.get("duration", 60)
            _ramp(series["spo2"], onset, d, 97, 87)
            _ramp(series["rr"], onset, d, 15, 28)
            _ramp(series["hr"], onset, d, 78, 118)
            on_oxygen[onset + int(d * 40 / 60):] = True
            labels.append(_label(pid, sc, start, onset, onset + d))
        elif sc == "hypotension":
            sbp0 = float(series["sbp"][onset])
            hr0 = float(series["hr"][onset])
            _ramp(series["sbp"], onset, 45, sbp0, 82)
            _ramp(series["hr"], onset, 45, hr0, hr0 + 25)
            labels.append(_label(pid, sc, start, onset, onset + 45))
        elif sc == "tachy_spike":
            series["hr"][onset:onset + 3] = 155
            labels.append(_label(pid, sc, start, onset, onset + 3))
        elif sc == "sensor_artifact":
            second = ev.get("second", onset + 25)
            series["spo2"][onset] = 0
            if second < minutes:
                series["hr"][second] = 400
            labels.append(_label(pid, sc, start, onset, min(second, minutes - 1) + 1))
        elif sc == "night_agitation":
            end = min(onset + ev.get("duration", 90), minutes)
            activity[onset:end] = np.clip(rng.normal(85, 8, end - onset), 0, 100)
            in_bed[onset + 30:min(onset + 40, minutes)] = False
            labels.append(_label(pid, sc, start, onset, end))
        elif sc == "inactivity":
            end = min(onset + 150, minutes)
            activity[onset:end] = rng.uniform(0, 2, end - onset)
            in_bed[onset:end] = True
            labels.append(_label(pid, sc, start, onset, end))
        elif sc == "rx_risky":
            h = ev.get("heparin", onset)
            k = ev.get("ketorolac", onset + 120)
            i = ev.get("insulin", onset + 360)
            add_rx(0, "insulina", 10, "UI", "start", "SC")
            add_rx(h, "heparina", 5000, "UI", "start", "SC")
            add_rx(k, "cetorolaco", 30, "mg", "start")
            add_rx(i, "insulina", 20, "UI", "change", "SC")
            if k < minutes:
                labels.append(_label(pid, "rx_interaction", start, k, k + 1))
            if i < minutes:
                labels.append(_label(pid, "rx_dose_change", start, i, i + 1))
        else:
            raise ValueError(f"cenário desconhecido: {sc}")

    rx.sort(key=lambda e: e.ts)
    vitals, moves = [], []
    for i in range(minutes):
        vitals.append(VitalObservation(
            patient_id=pid, ts=ts[i], hr=round(float(series["hr"][i]), 1),
            sbp=round(float(series["sbp"][i]), 1), dbp=round(float(series["dbp"][i]), 1),
            spo2=round(float(series["spo2"][i]), 1), rr=round(float(series["rr"][i]), 1),
            temp=round(float(series["temp"][i]), 2), on_oxygen=bool(on_oxygen[i])))
        moves.append(MovementSample(patient_id=pid, ts=ts[i],
                                    activity_count=round(float(activity[i]), 1),
                                    in_bed=bool(in_bed[i]), source="sensor"))
    return vitals, rx, moves, labels


def generate_patient_timeline(patient_id: str, start: datetime, minutes: int, scenario: str,
                              seed: int, onset_min: int | None = None):
    """Gera (vitais, prescrições, movimento, rótulos de verdade) de um paciente."""
    if scenario not in SCENARIOS:
        raise ValueError(f"cenário desconhecido: {scenario}")
    if scenario == "demo":
        raise ValueError("use demo_timeline() para o cenário demo")
    return build_timeline(patient_id, start, minutes, seed,
                          [{"scenario": scenario, "onset": onset_min}])


DEMO_MINUTES = 480


def demo_timeline(patient_id: str, start: datetime, seed: int = 0):
    """Linha do tempo de um dos pacientes P-0001..P-0005 do cenário demo (seção 7.1)."""
    spec = {
        "P-0001": dict(events=[dict(scenario="respiratory_deterioration", onset=375,
                                    duration=30)]),
        "P-0002": dict(events=[dict(scenario="rx_risky", onset=380, heparin=380,
                                    ketorolac=390, insulin=400)]),
        "P-0003": dict(events=[]),
        "P-0004": dict(events=[dict(scenario="night_agitation", onset=360, duration=90)],
                       extra_rx=[(300, "morfina", 5, "start")]),
        "P-0005": dict(events=[dict(scenario="sensor_artifact", onset=370, second=395)]),
    }[patient_id]
    return build_timeline(patient_id, start, DEMO_MINUTES, seed, spec["events"],
                          spec.get("extra_rx"))
