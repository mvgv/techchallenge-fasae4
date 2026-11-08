"""Carrega o MIMIC-IV Demo (já preparado em parquet) como modelos de contrato."""
from pathlib import Path

import pandas as pd

from medwatch.contracts import PrescriptionEvent, VitalObservation

MIMIC_DIR = Path("data/mimic")
_VITAL_FIELDS = ("hr", "sbp", "dbp", "spo2", "rr", "temp")


def _num(x) -> float | None:
    return None if pd.isna(x) else float(x)


def load_mimic(limit_patients: int, root: Path | None = None):
    """Retorna (vitais, prescrições) dos primeiros `limit_patients` pacientes."""
    root = root or MIMIC_DIR
    vit_path, rx_path = root / "vitals.parquet", root / "prescriptions.parquet"
    if not vit_path.exists() or not rx_path.exists():
        raise FileNotFoundError(
            "MIMIC não preparado: rode scripts/download_mimic_demo.sh (ou prepare_mimic.py)")
    vdf = pd.read_parquet(vit_path)
    rdf = pd.read_parquet(rx_path)
    ids = sorted(vdf["patient_id"].unique())[:limit_patients]
    vitals = []
    for r in vdf[vdf["patient_id"].isin(ids)].sort_values("ts").to_dict("records"):
        vitals.append(VitalObservation(
            patient_id=r["patient_id"], ts=pd.Timestamp(r["ts"]).to_pydatetime(),
            **{k: _num(r.get(k)) for k in _VITAL_FIELDS}))
    rx = []
    for n, r in enumerate(rdf[rdf["patient_id"].isin(ids)].sort_values("ts").to_dict("records")):
        rx.append(PrescriptionEvent(
            rx_id=f"{r['patient_id']}-rx{n}", patient_id=r["patient_id"],
            ts=pd.Timestamp(r["ts"]).to_pydatetime(), drug=str(r["drug"]),
            dose=_num(r.get("dose")),
            unit=None if pd.isna(r.get("unit")) else str(r["unit"]),
            route=None if pd.isna(r.get("route")) else str(r["route"]), action="start"))
    return vitals, rx
