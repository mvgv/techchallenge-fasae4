"""Carrega o MIMIC-IV Demo (já preparado em parquet) como modelos de contrato."""
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

from medwatch.config import load_yaml
from medwatch.contracts import PrescriptionEvent, VitalObservation

MIMIC_DIR = Path("data/mimic")
_VITAL_FIELDS = ("hr", "sbp", "dbp", "spo2", "rr", "temp")


def _num(x) -> float | None:
    return None if pd.isna(x) else float(x)


def split_patients(split: str, splits_path: Path | None = None) -> list[str]:
    """IDs da parte `split` da seção `mimic` de config/splits.yaml."""
    data = (yaml.safe_load(splits_path.read_text(encoding="utf-8"))
            if splits_path else load_yaml("splits"))
    try:
        return list(data["mimic"][split])
    except KeyError as e:
        raise KeyError(f"divisão '{split}' do MIMIC não existe em splits.yaml") from e


def load_mimic_frames(limit_patients: int | None = None, root: Path | None = None,
                      split: str | None = None, rebase_start: datetime | None = None,
                      window_hours: float | None = None,
                      splits_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """DataFrames (vitais, prescrições) filtrados por divisão e com datas deslocadas.

    `rebase_start` desloca cada paciente para que a primeira observação de vitais caia
    nesse instante, mantendo os intervalos; `window_hours` mantém só as primeiras N horas
    de cada paciente (contadas da primeira observação de vitais).
    """
    root = root or MIMIC_DIR
    vit_path, rx_path = root / "vitals.parquet", root / "prescriptions.parquet"
    if not vit_path.exists() or not rx_path.exists():
        raise FileNotFoundError(
            "MIMIC não preparado: rode scripts/download_datasets.py --mimic")
    vdf = pd.read_parquet(vit_path)
    rdf = pd.read_parquet(rx_path)
    ids = sorted(vdf["patient_id"].unique())
    if split:
        wanted = set(split_patients(split, splits_path))
        ids = [i for i in ids if i in wanted]
    if limit_patients is not None:
        ids = ids[:limit_patients]
    vdf = vdf[vdf["patient_id"].isin(ids)].copy()
    rdf = rdf[rdf["patient_id"].isin(ids)].copy()
    first = vdf.groupby("patient_id")["ts"].min()
    if window_hours is not None:
        end = first + pd.Timedelta(hours=window_hours)
        vdf = vdf[vdf["ts"] <= vdf["patient_id"].map(end)]
        rdf = rdf[(rdf["ts"] >= rdf["patient_id"].map(first))
                  & (rdf["ts"] <= rdf["patient_id"].map(end))]
    if rebase_start is not None:
        shift = pd.Timestamp(rebase_start) - first
        vdf["ts"] = vdf["ts"] + vdf["patient_id"].map(shift)
        rdf["ts"] = rdf["ts"] + rdf["patient_id"].map(shift)
    return (vdf.sort_values(["ts", "patient_id"]).reset_index(drop=True),
            rdf.sort_values(["ts", "patient_id"]).reset_index(drop=True))


def frames_to_models(vdf: pd.DataFrame, rdf: pd.DataFrame
                     ) -> tuple[list[VitalObservation], list[PrescriptionEvent]]:
    """Converte os DataFrames do MIMIC em modelos de contrato."""
    vitals = [VitalObservation(
        patient_id=r["patient_id"], ts=pd.Timestamp(r["ts"]).to_pydatetime(),
        **{k: _num(r.get(k)) for k in _VITAL_FIELDS}) for r in vdf.to_dict("records")]
    rx = []
    for n, r in enumerate(rdf.to_dict("records")):
        rx.append(PrescriptionEvent(
            rx_id=f"{r['patient_id']}-rx{n}", patient_id=r["patient_id"],
            ts=pd.Timestamp(r["ts"]).to_pydatetime(), drug=str(r["drug"]),
            dose=_num(r.get("dose")),
            unit=None if pd.isna(r.get("unit")) else str(r["unit"]),
            route=None if pd.isna(r.get("route")) else str(r["route"]), action="start"))
    return vitals, rx


def load_mimic(limit_patients: int | None = None, root: Path | None = None,
               split: str | None = None, rebase_start: datetime | None = None,
               window_hours: float | None = None, splits_path: Path | None = None):
    """Retorna (vitais, prescrições) dos pacientes escolhidos, em ordem de tempo."""
    vdf, rdf = load_mimic_frames(limit_patients, root, split, rebase_start, window_hours,
                                 splits_path)
    return frames_to_models(vdf, rdf)
