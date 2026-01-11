from __future__ import annotations

import pandas as pd
import streamlit as st


def render_overview(dff: pd.DataFrame) -> None:
    # --- Top dogs with rank
    top = (
        dff.groupby("dog_name", as_index=False)["distance_km"]
        .sum()
        .sort_values("distance_km", ascending=False)
        .head(10)
    )

    top_ranked = top.reset_index(drop=True)
    top_ranked.insert(0, "rank", top_ranked.index + 1)
    top_ranked["distance_km"] = top_ranked["distance_km"].round(1)

    # --- Daily sum
    daily = (
        dff.assign(date=dff["date"].dt.floor("D"))
        .groupby("date", as_index=False)["distance_km"]
        .sum()
        .sort_values("date")
    )

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Top-10 dogs by total km")
        st.dataframe(top_ranked, use_container_width=True, hide_index=True)

    with c2:
        st.subheader("Total km per day")
        st.line_chart(daily.set_index("date"))
