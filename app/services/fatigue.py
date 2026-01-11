from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date, timedelta

import pandas as pd
from sqlalchemy import text

from app.db import engine


@dataclass(frozen=True)
class FatigueConfig:
    hard_day_threshold_km: float = 18.0
    hard_streak_days: int = 3
    lookback_days_3: int = 3
    lookback_days_7: int = 7


def load_training_window(day: Date, lookback_days: int) -> pd.DataFrame:
    """
    Load training logs for [day - lookback_days, day] inclusive.
    """
    start = (day - timedelta(days=lookback_days)).isoformat()
    end = day.isoformat()

    q = """
    SELECT d.name AS dog_name, t.date, t.distance_km
    FROM training_log t
    JOIN dogs d ON d.id = t.dog_id
    WHERE t.date >= :start AND t.date <= :end
    ORDER BY t.date, d.name
    """
    df = pd.read_sql(text(q), engine, params={"start": start, "end": end})
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"]).dt.floor("D")
    df["distance_km"] = pd.to_numeric(df["distance_km"], errors="coerce").fillna(0.0)
    return df


def compute_fatigue(day: Date, cfg: FatigueConfig) -> pd.DataFrame:
    """
    Returns per-dog metrics and fatigue score for a planned run on 'day'.
    Uses recent workload up to 'day' (inclusive).
    """
    df = load_training_window(day=day, lookback_days=max(cfg.lookback_days_7, cfg.lookback_days_3))
    if df.empty:
        return pd.DataFrame(columns=["dog_name", "km_3d", "km_7d", "last_day_km", "hard_streak", "fatigue"])

    df["day"] = df["date"].dt.date

    # daily km per dog
    daily = (
        df.groupby(["dog_name", "day"], as_index=False)["distance_km"]
        .sum()
        .sort_values(["dog_name", "day"])
    )

    # compute windows
    day_list_3 = {day - timedelta(days=i) for i in range(cfg.lookback_days_3)}
    day_list_7 = {day - timedelta(days=i) for i in range(cfg.lookback_days_7)}

    km_3d = (
        daily[daily["day"].isin(day_list_3)]
        .groupby("dog_name", as_index=False)["distance_km"]
        .sum()
        .rename(columns={"distance_km": "km_3d"})
    )
    km_7d = (
        daily[daily["day"].isin(day_list_7)]
        .groupby("dog_name", as_index=False)["distance_km"]
        .sum()
        .rename(columns={"distance_km": "km_7d"})
    )

    last_day = day  # we evaluate including current day if exists
    last_day_km = (
        daily[daily["day"] == last_day]
        .groupby("dog_name", as_index=False)["distance_km"]
        .sum()
        .rename(columns={"distance_km": "last_day_km"})
    )

    # hard streak (consecutive hard days ending at 'day')
    daily["is_hard"] = daily["distance_km"] >= float(cfg.hard_day_threshold_km)
    streaks = []
    for dog, g in daily.groupby("dog_name", sort=False):
        g = g.sort_values("day").copy()
        # only consider recent 14-ish days present in df
        hard_map = dict(zip(g["day"], g["is_hard"]))
        cur = 0
        d = day
        while d in hard_map and hard_map[d]:
            cur += 1
            d = d - timedelta(days=1)
        streaks.append({"dog_name": dog, "hard_streak": int(cur)})

    streak_df = pd.DataFrame(streaks)

    # merge
    out = pd.DataFrame({"dog_name": daily["dog_name"].unique()})
    out = out.merge(km_3d, on="dog_name", how="left")
    out = out.merge(km_7d, on="dog_name", how="left")
    out = out.merge(last_day_km, on="dog_name", how="left")
    out = out.merge(streak_df, on="dog_name", how="left")
    out = out.fillna({"km_3d": 0.0, "km_7d": 0.0, "last_day_km": 0.0, "hard_streak": 0})

    # fatigue score (simple + explainable)
    # penalty if streak >= 2 (so it grows)
    out["fatigue"] = (
        0.55 * out["km_7d"]
        + 0.35 * out["km_3d"]
        + 0.10 * out["last_day_km"]
        + 10.0 * (out["hard_streak"].clip(lower=0) - 1).clip(lower=0)
    )

    return out.sort_values("fatigue", ascending=True).reset_index(drop=True)
