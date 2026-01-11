from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from app.db import engine


def load_data() -> pd.DataFrame:
    q = """
    SELECT d.name AS dog_name, t.date, t.distance_km
    FROM training_log t
    JOIN dogs d ON d.id = t.dog_id
    ORDER BY t.date, d.name
    """
    df = pd.read_sql(text(q), engine)
    df["date"] = pd.to_datetime(df["date"])
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce").fillna(0.0)
    return df
