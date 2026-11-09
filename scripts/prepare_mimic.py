"""Converte o MIMIC-IV Demo em data/mimic/vitals.parquet e prescriptions.parquet."""
import sys
from pathlib import Path

import pandas as pd

ITEMS = {220045: "hr", 220179: "sbp", 220180: "dbp", 220277: "spo2", 220210: "rr",
         223761: "temp_f", 223762: "temp_c", 220050: "sbp_art", 220051: "dbp_art"}


def prepare(root: Path) -> None:
    ce = pd.read_csv(root / "icu" / "chartevents.csv.gz",
                     usecols=["subject_id", "charttime", "itemid", "valuenum"])
    ce = ce[ce["itemid"].isin(ITEMS)].dropna(subset=["valuenum"]).copy()
    ce["var"] = ce["itemid"].map(ITEMS)
    ce["ts"] = pd.to_datetime(ce["charttime"], utc=True).dt.round("5min")
    v = ce.pivot_table(index=["subject_id", "ts"], columns="var", values="valuenum",
                       aggfunc="mean").reset_index()
    # Temperatura: Celsius medido tem prioridade; senão converte de Fahrenheit.
    temp_f = (v.pop("temp_f") - 32) * 5 / 9 if "temp_f" in v else None
    temp_c = v.pop("temp_c") if "temp_c" in v else None
    v["temp"] = temp_c.fillna(temp_f) if temp_c is not None and temp_f is not None else (
        temp_c if temp_c is not None else temp_f)
    # Pressão: não invasiva tem prioridade; a arterial (invasiva) preenche as lacunas.
    for col in ("sbp", "dbp"):
        art = v.pop(f"{col}_art") if f"{col}_art" in v else None
        if art is not None:
            v[col] = v[col].fillna(art) if col in v else art
    v["patient_id"] = "M-" + v["subject_id"].astype(str)
    v = v.drop(columns="subject_id")
    v.to_parquet(root / "vitals.parquet", index=False)

    rx = pd.read_csv(root / "hosp" / "prescriptions.csv.gz",
                     usecols=["subject_id", "starttime", "drug", "dose_val_rx",
                              "dose_unit_rx", "route"])
    rx = rx.dropna(subset=["starttime", "drug"]).copy()
    rx["patient_id"] = "M-" + rx["subject_id"].astype(str)
    rx["ts"] = pd.to_datetime(rx["starttime"], utc=True)
    rx["dose"] = pd.to_numeric(rx["dose_val_rx"], errors="coerce")
    rx = rx.rename(columns={"dose_unit_rx": "unit"})[
        ["patient_id", "ts", "drug", "dose", "unit", "route"]]
    rx.to_parquet(root / "prescriptions.parquet", index=False)
    print(f"{len(v)} linhas de vitais, {len(rx)} prescrições gravadas em {root}")


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mimic")
    sub = next(base.rglob("chartevents.csv.gz")).parent.parent
    prepare(sub if sub != base else base)
