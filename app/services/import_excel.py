from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import pandas as pd

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dog, TrainingLog


@dataclass(frozen=True)
class ImportResult:
    dogs_created: int
    rows_inserted: int
    rows_skipped_duplicates: int


def import_wide_month_sheet(
    *,
    session: Session,
    excel_path: Path,
    sheet_name: str,
    source_label: str,
    treat_zero_as_missing: bool = False,
) -> ImportResult:
    """
    Excel sheet format:
      dog_name | 2025-12-01 | 2025-12-02 | ... | 2025-12-31
    where date columns are headers (preferably TEXT "YYYY-MM-DD")
    and values are numbers (km).
    """
    df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")

    if df.empty:
        return ImportResult(0, 0, 0)

    # Normalize header
    df.columns = [str(c).strip() for c in df.columns]
    if "dog_name" not in df.columns:
        raise ValueError("Sheet must contain 'dog_name' as the first column header.")

    # Melt wide -> long
    date_cols = [c for c in df.columns if c != "dog_name"]
    long_df = df.melt(id_vars=["dog_name"], value_vars=date_cols, var_name="date", value_name="distance_km")

    # Clean
    long_df["dog_name"] = long_df["dog_name"].astype(str).str.strip()

    # Parse dates from headers
    long_df["date"] = pd.to_datetime(long_df["date"], format="%Y-%m-%d", errors="raise").dt.date

    # Coerce km to numeric
    long_df["distance_km"] = pd.to_numeric(long_df["distance_km"], errors="coerce")

    # Drop empty rows (no dog or no value)
    long_df = long_df.dropna(subset=["distance_km"])
    long_df = long_df[long_df["dog_name"] != ""]

    if treat_zero_as_missing:
        long_df = long_df[long_df["distance_km"] != 0]

    # 1) Ensure dogs exist
    existing = session.execute(select(Dog.name, Dog.id)).all()
    name_to_id = {name: did for name, did in existing}

    dogs_created = 0
    for name in sorted(set(long_df["dog_name"].tolist())):
        if name not in name_to_id:
            d = Dog(name=name)
            session.add(d)
            session.flush()  # get id
            name_to_id[name] = d.id
            dogs_created += 1

    # 2) Insert training rows (skip duplicates)
    rows_inserted = 0
    rows_skipped = 0

    # preload existing keys for this source to skip duplicates fast
    existing_keys = set(
        session.execute(
            select(TrainingLog.dog_id, TrainingLog.date).where(TrainingLog.source == source_label)
        ).all()
    )

    to_add = []
    for r in long_df.itertuples(index=False):
        dog_id = name_to_id[r.dog_name]
        key = (dog_id, r.date)
        if key in existing_keys:
            rows_skipped += 1
            continue
        to_add.append(TrainingLog(dog_id=dog_id, date=r.date, distance_km=float(r.distance_km), source=source_label))
        existing_keys.add(key)

    session.add_all(to_add)
    rows_inserted = len(to_add)

    return ImportResult(dogs_created, rows_inserted, rows_skipped)
