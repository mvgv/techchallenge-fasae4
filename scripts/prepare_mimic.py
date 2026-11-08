"""Converte o MIMIC-IV Demo em data/mimic/vitals.parquet e prescriptions.parquet."""
import sys
from pathlib import Path

import pandas as pd

ITEMS = {220045: "hr", 220179: "sbp", 220180: "dbp", 220277: "spo2", 220210: "rr",
         223761: "temp_f"}


def prepare(root: Path) -> None:
    ce = pd.read_csv(root / "icu" / "chartevents.csv.gz",
                     usecols=["subject_id", "charttime", "itemid", "valuenum"])
    ce = ce[ce["itemid"].isin(ITEMS)].dropna(subset=["valuenum"]).copy()
    ce["var"] = ce["itemid"].map(ITEMS)
    ce["ts"] = pd.to_datetime(ce["charttime"], utc=True).dt.round("5min")
    v = ce.pivot_table(index=["subject_id", "ts"], columns="var", values="valuenum",
                       aggfunc="mean").reset_index()
    if "temp_f" in v:
        v["temp"] = (v.pop("temp_f") - 32) * 5 / 9
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
