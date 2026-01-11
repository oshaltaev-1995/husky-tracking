from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class ExportResult:
    path: Path
    sheet_name: str
    rows: int
    dogs: int
    days: int


def export_tracking_wide(
    dff: pd.DataFrame,
    date_from: Date,
    date_to: Date,
    out_dir: Path,
) -> ExportResult:
    """
    Export to Excel in the same wide format as your demo sheet:
    dog_name | YYYY-MM-DD | YYYY-MM-DD | ...
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    df = dff.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.floor("D")
    df["day"] = df["date"].dt.strftime("%Y-%m-%d")
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce").fillna(0.0)

    wide = (
        df.groupby(["dog_name", "day"], as_index=False)["distance_km"]
        .sum()
        .pivot(index="dog_name", columns="day", values="distance_km")
        .fillna(0.0)
    )

    # make sure all days exist as columns (even if missing)
    all_days = pd.date_range(date_from, date_to, freq="D").strftime("%Y-%m-%d").tolist()
    for d in all_days:
        if d not in wide.columns:
            wide[d] = 0.0
    wide = wide[all_days]  # reorder

    wide = wide.reset_index()
    wide.insert(0, "dog_name", wide.pop("dog_name"))

    # sheet name like your pattern
    sheet_name = f"tracking_{date_from.strftime('%Y-%m')}"
    if date_from.strftime("%Y-%m") != date_to.strftime("%Y-%m"):
        sheet_name = f"tracking_{date_from.strftime('%Y-%m')}_to_{date_to.strftime('%Y-%m')}"

    filename = f"tracking_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.xlsx"
    path = out_dir / filename

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        wide.to_excel(writer, sheet_name=sheet_name, index=False)

    return ExportResult(
        path=path,
        sheet_name=sheet_name,
        rows=int(wide.shape[0]),
        dogs=int(df["dog_name"].nunique()),
        days=len(all_days),
    )
