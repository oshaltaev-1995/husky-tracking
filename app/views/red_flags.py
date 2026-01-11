from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st


@dataclass(frozen=True)
class Thresholds:
    hard_day_threshold: int
    hard_streak_days: int
    hard_days_share: int
    week_threshold: int


def thresholds_ui() -> Thresholds:
    st.subheader("Red flags (workload alerts)")
    st.caption("These alerts focus on hard days and accumulated load (works even without dog age/metadata).")

    s1, s2, s3, s4 = st.columns(4)

    with s1:
        hard_day_threshold = st.slider(
            "Hard day threshold (km)",
            0, 60,
            value=int(st.session_state.get("rf_hard_day", 18)),
            step=1,
            key="rf_hard_day",
        )

    with s2:
        hard_streak_days = st.slider(
            "Hard-day streak (days)",
            2, 10,
            value=int(st.session_state.get("rf_streak", 3)),
            step=1,
            key="rf_streak",
        )

    with s3:
        hard_days_share = st.slider(
            "Hard days share (%)",
            0, 100,
            value=int(st.session_state.get("rf_share", 40)),
            step=5,
            key="rf_share",
        )

    with s4:
        week_threshold = st.slider(
            "7-day total threshold (km)",
            0, 500,
            value=int(st.session_state.get("rf_week", 180)),
            step=5,
            key="rf_week",
        )

    return Thresholds(
        hard_day_threshold=hard_day_threshold,
        hard_streak_days=hard_streak_days,
        hard_days_share=hard_days_share,
        week_threshold=week_threshold,
    )


def render_red_flags(dff: pd.DataFrame) -> Thresholds:
    thr = thresholds_ui()

    # --- Daily per dog
    daily_dog = (
        dff.assign(date=dff["date"].dt.floor("D"))
        .groupby(["dog_name", "date"], as_index=False)["distance_km"]
        .sum()
        .sort_values(["dog_name", "date"])
    )

    daily_dog["is_hard"] = daily_dog["distance_km"] >= thr.hard_day_threshold

    # --- Flag A: hard days
    hard_days_df = daily_dog[daily_dog["is_hard"]].copy()

    # --- Flag B: hard-day streaks
    streak_rows = []
    for dog, g in daily_dog.groupby("dog_name", sort=False):
        g = g.sort_values("date").copy()
        grp = (g["is_hard"] != g["is_hard"].shift()).cumsum()
        for _, block in g[g["is_hard"]].groupby(grp):
            if len(block) >= thr.hard_streak_days:
                streak_rows.append(
                    {
                        "dog_name": dog,
                        "start_date": block["date"].min(),
                        "end_date": block["date"].max(),
                        "days": int(len(block)),
                        "avg_km": float(block["distance_km"].mean()),
                        "max_km": float(block["distance_km"].max()),
                    }
                )
    streak_df = pd.DataFrame(streak_rows)

    # --- Flag C: hard-day share
    share = (
        daily_dog.groupby("dog_name", as_index=False)
        .agg(
            days=("date", "nunique"),
            hard_days=("is_hard", "sum"),
            total_km=("distance_km", "sum"),
        )
    )
    share["hard_share_pct"] = (share["hard_days"] / share["days"] * 100).round(1)
    share_flag = share[share["hard_share_pct"] >= thr.hard_days_share].copy()

    # --- Flag D: 7-day rolling total
    roll_rows = []
    for dog, g in daily_dog.groupby("dog_name", sort=False):
        g = g.sort_values("date").copy().set_index("date")
        roll = g["distance_km"].rolling("7D").sum()
        bad = roll[roll >= thr.week_threshold]
        if not bad.empty:
            worst = bad.sort_values(ascending=False).head(3)
            for dt, val in worst.items():
                roll_rows.append({"dog_name": dog, "date": dt, "km_7d": float(val)})
    roll_df = pd.DataFrame(roll_rows)

    # --- Banner
    dogs_alert = set(share_flag["dog_name"].unique().tolist())
    if not streak_df.empty:
        dogs_alert |= set(streak_df["dog_name"].unique().tolist())
    if not roll_df.empty:
        dogs_alert |= set(roll_df["dog_name"].unique().tolist())

    if len(dogs_alert) == 0:
        st.success("✅ No alerts for current thresholds.")
    elif len(dogs_alert) <= 5:
        st.warning(f"⚠️ Alerts for {len(dogs_alert)} dog(s): {', '.join(sorted(dogs_alert))}")
    else:
        st.error(f"🚨 Alerts for {len(dogs_alert)} dogs. Review workload and rest plan.")

    # --- Metrics row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Dogs with hard days", int(hard_days_df["dog_name"].nunique()))
    with m2:
        st.metric("Dogs with hard streaks", int(streak_df["dog_name"].nunique()) if not streak_df.empty else 0)
    with m3:
        st.metric("Dogs with high hard-day share", int(share_flag["dog_name"].nunique()) if not share_flag.empty else 0)
    with m4:
        st.metric("Dogs with 7-day overload", int(roll_df["dog_name"].nunique()) if not roll_df.empty else 0)

    # --- Most critical dogs (severity)
    score = share.set_index("dog_name")[["total_km", "hard_share_pct"]].copy()

    if not streak_df.empty:
        score = score.join(
            streak_df.groupby("dog_name")["days"].max().rename("max_hard_streak"),
            how="left",
        )
    else:
        score["max_hard_streak"] = 0

    if not roll_df.empty:
        score = score.join(
            roll_df.groupby("dog_name")["km_7d"].max().rename("max_7d"),
            how="left",
        )
    else:
        score["max_7d"] = 0

    score = score.fillna(0)
    score["severity"] = (
        (score["hard_share_pct"] / max(thr.hard_days_share, 1))
        + (score["max_hard_streak"] / max(thr.hard_streak_days, 1))
        + (score["max_7d"] / max(thr.week_threshold, 1))
    )

    st.caption("Most critical dogs (combined severity)")
    crit = score.sort_values("severity", ascending=False).head(10).reset_index()
    crit["total_km"] = crit["total_km"].round(1)
    crit["hard_share_pct"] = crit["hard_share_pct"].round(1)
    crit["max_7d"] = crit["max_7d"].round(1)
    crit["severity"] = crit["severity"].round(2)
    st.dataframe(crit, use_container_width=True, hide_index=True)

    st.divider()

    # --- Tables
    t1, t2, t3, t4 = st.columns(4)

    with t1:
        st.caption(f"Hard days (>= {thr.hard_day_threshold} km)")
        if hard_days_df.empty:
            st.info("No hard days for current settings.")
        else:
            view = hard_days_df.copy()
            view["date"] = view["date"].dt.strftime("%Y-%m-%d")
            view["distance_km"] = view["distance_km"].round(1)
            st.dataframe(
                view.sort_values(["distance_km", "date"], ascending=[False, True]).head(50),
                use_container_width=True,
                hide_index=True,
            )

    with t2:
        st.caption(f"Hard streaks (>= {thr.hard_day_threshold} km for {thr.hard_streak_days}+ days)")
        if streak_df.empty:
            st.info("No hard streaks for current settings.")
        else:
            view = streak_df.copy()
            view["start_date"] = pd.to_datetime(view["start_date"]).dt.strftime("%Y-%m-%d")
            view["end_date"] = pd.to_datetime(view["end_date"]).dt.strftime("%Y-%m-%d")
            view["avg_km"] = view["avg_km"].round(1)
            view["max_km"] = view["max_km"].round(1)
            st.dataframe(
                view.sort_values(["days", "max_km"], ascending=[False, False]),
                use_container_width=True,
                hide_index=True,
            )

    with t3:
        st.caption(f"Hard-day share (>= {thr.hard_days_share}%)")
        if share_flag.empty:
            st.info("No dogs exceed hard-day share threshold.")
        else:
            view = share_flag.copy()
            view["hard_share_pct"] = view["hard_share_pct"].round(1)
            view["total_km"] = view["total_km"].round(1)
            st.dataframe(
                view.sort_values(["hard_share_pct", "total_km"], ascending=[False, False]),
                use_container_width=True,
                hide_index=True,
            )

    with t4:
        st.caption(f"7-day overload (>= {thr.week_threshold} km)")
        if roll_df.empty:
            st.info("No 7-day overload for current settings.")
        else:
            view = roll_df.copy()
            view["date"] = pd.to_datetime(view["date"]).dt.strftime("%Y-%m-%d")
            view["km_7d"] = view["km_7d"].round(1)
            st.dataframe(
                view.sort_values("km_7d", ascending=False),
                use_container_width=True,
                hide_index=True,
            )

    return thr
