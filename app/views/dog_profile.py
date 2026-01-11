from __future__ import annotations

import pandas as pd
import streamlit as st

from app.views.red_flags import Thresholds


def _thresholds_sidebar_in_profile() -> Thresholds:
    """
    Threshold controls inside Dog profile tab.
    Widget keys are unique (dp_*), but values are synced to shared rf_* in session_state.
    """
    st.caption("Alert thresholds (synced with Red flags tab)")

    # initial defaults from shared rf_* (if exist)
    rf_day = int(st.session_state.get("rf_hard_day", 18))
    rf_streak = int(st.session_state.get("rf_streak", 3))
    rf_share = int(st.session_state.get("rf_share", 40))
    rf_week = int(st.session_state.get("rf_week", 180))

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        hard_day_threshold = st.slider(
            "Hard day (km)",
            0, 60,
            value=rf_day,
            step=1,
            key="dp_rf_hard_day",
        )
    with s2:
        hard_streak_days = st.slider(
            "Hard streak (days)",
            2, 10,
            value=rf_streak,
            step=1,
            key="dp_rf_streak",
        )
    with s3:
        hard_days_share = st.slider(
            "Hard days share (%)",
            0, 100,
            value=rf_share,
            step=5,
            key="dp_rf_share",
        )
    with s4:
        week_threshold = st.slider(
            "7-day total (km)",
            0, 500,
            value=rf_week,
            step=5,
            key="dp_rf_week",
        )

    # sync back to shared rf_* values (used by Red flags)
    st.session_state["rf_hard_day"] = hard_day_threshold
    st.session_state["rf_streak"] = hard_streak_days
    st.session_state["rf_share"] = hard_days_share
    st.session_state["rf_week"] = week_threshold

    return Thresholds(
        hard_day_threshold=hard_day_threshold,
        hard_streak_days=hard_streak_days,
        hard_days_share=hard_days_share,
        week_threshold=week_threshold,
    )


def render_dog_profile(dff: pd.DataFrame, thr: Thresholds | None = None) -> None:
    st.subheader("Dog profile")

    dog_list = sorted(dff["dog_name"].unique().tolist())
    selected_dog = st.selectbox("Select dog", dog_list, key="dog_profile_select")

    dog_df = dff[dff["dog_name"] == selected_dog].copy()
    dog_df = dog_df.assign(date=dog_df["date"].dt.floor("D"))

    dog_daily = (
        dog_df.groupby("date", as_index=False)["distance_km"]
        .sum()
        .sort_values("date")
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total km", float(dog_daily["distance_km"].sum()))
    with c2:
        st.metric("Days with runs", int((dog_daily["distance_km"] > 0).sum()))
    avg_km = dog_daily.loc[dog_daily["distance_km"] > 0, "distance_km"].mean()
    with c3:
        st.metric("Avg km/day (runs only)", round(float(avg_km), 2) if avg_km is not None else 0.0)

    st.line_chart(dog_daily.set_index("date"))

    st.divider()
    st.subheader("Alerts for this dog")

    # show thresholds controls here (synced with Red flags)
    thr = _thresholds_sidebar_in_profile()

    # daily series for selected dog
    dog_series = (
        dff[dff["dog_name"] == selected_dog]
        .assign(date=lambda x: x["date"].dt.floor("D"))
        .groupby("date", as_index=False)["distance_km"]
        .sum()
        .sort_values("date")
    )

    dog_series["is_hard"] = dog_series["distance_km"] >= thr.hard_day_threshold

    # hard share
    days_total = int(dog_series["date"].nunique())
    hard_days_cnt = int(dog_series["is_hard"].sum())
    hard_share_pct = (hard_days_cnt / days_total * 100) if days_total else 0.0

    # max hard streak
    max_streak = 0
    cur = 0
    for v in dog_series["is_hard"].tolist():
        if v:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0

    # max 7-day rolling total
    dog_roll = dog_series.set_index("date")["distance_km"].rolling("7D").sum()
    max_7d = float(dog_roll.max()) if not dog_roll.empty else 0.0

    # status
    triggers = []
    if max_streak >= thr.hard_streak_days:
        triggers.append("hard-day streak")
    if hard_share_pct >= thr.hard_days_share:
        triggers.append("high hard-day share")
    if max_7d >= thr.week_threshold:
        triggers.append("7-day overload")

    if not triggers:
        st.success("✅ No alerts for this dog with current thresholds.")
    else:
        st.error("🚨 Alert: " + ", ".join(triggers))

    a1, a2, a3 = st.columns(3)
    with a1:
        st.metric("Hard days", f"{hard_days_cnt}/{days_total} ({hard_share_pct:.1f}%)")
    with a2:
        st.metric("Max hard streak", f"{max_streak} days")
    with a3:
        st.metric("Max 7-day total", f"{max_7d:.1f} km")

    st.divider()
    st.caption("Top days by distance")
    top_days = dog_daily.sort_values("distance_km", ascending=False).head(10)
    top_days_view = top_days.copy()
    top_days_view["date"] = top_days_view["date"].dt.strftime("%Y-%m-%d")
    top_days_view["distance_km"] = top_days_view["distance_km"].round(1)
    st.dataframe(top_days_view.reset_index(drop=True), use_container_width=True, hide_index=True)
