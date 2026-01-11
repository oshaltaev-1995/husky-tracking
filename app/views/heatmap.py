from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st


def render_heatmap(dff: pd.DataFrame) -> None:
    st.subheader("Heatmap: km per dog per day")

    if dff.empty:
        st.info("No data for selected period.")
        return

    heat = dff.copy()
    heat["day_ts"] = pd.to_datetime(heat["date"]).dt.floor("D")
    heat["day"] = heat["day_ts"].dt.strftime("%Y-%m-%d")
    heat["distance_km"] = pd.to_numeric(heat["distance_km"], errors="coerce").fillna(0.0)

    # 1 dog + 1 day -> 1 value
    heat = heat.groupby(["dog_name", "day"], as_index=False)["distance_km"].sum()

    max_available = int(heat["dog_name"].nunique())
    if max_available == 0:
        st.info("No dogs found in selected period.")
        return

    # Slider bounds must satisfy min < max (Streamlit requirement)
    if max_available == 1:
        st.info("Only one dog in selected period — heatmap is limited.")
        max_dogs = 1
    else:
        min_slider = 1
        max_slider = max_available

        default_show = min(30, max_available)
        default_show = max(min_slider, min(default_show, max_slider))

        step = 1 if max_slider < 10 else 5

        max_dogs = st.slider(
            "Max dogs to show",
            min_value=min_slider,
            max_value=max_slider,
            value=default_show,
            step=step,
            key="heatmap_max_dogs",
        )

    tall_mode = st.checkbox(
        "Tall mode (better when showing many dogs)",
        value=(max_dogs >= 20),
        key="heatmap_tall_mode",
    )

    # order dogs by total km (top N)
    dog_order = (
        heat.groupby("dog_name")["distance_km"]
        .sum()
        .sort_values(ascending=False)
        .head(max_dogs)
        .index
        .tolist()
    )

    heat = heat[heat["dog_name"].isin(dog_order)]
    day_order = sorted(heat["day"].unique().tolist())

    # fixed legend scale within the selected period
    vmin = float(pd.to_numeric(dff["distance_km"], errors="coerce").min())
    vmax = float(pd.to_numeric(dff["distance_km"], errors="coerce").max())

    # avoid degenerate scale if all values are the same
    if vmin == vmax:
        vmax = vmin + 1.0

    if tall_mode:
        chart_height = max(420, 22 * len(dog_order) + 120)
    else:
        chart_height = 420

    chart = (
        alt.Chart(heat)
        .mark_rect(stroke="rgba(255,255,255,0.18)", strokeWidth=0.8)
        .encode(
            x=alt.X(
                "day:O",
                title="Day",
                sort=day_order,
                axis=alt.Axis(labelAngle=90, labelOverlap=False),
            ),
            y=alt.Y(
                "dog_name:N",
                title="Dog",
                sort=dog_order,
                axis=alt.Axis(labelLimit=240),
            ),
            color=alt.Color(
                "distance_km:Q",
                title="Km",
                scale=alt.Scale(domain=[vmin, vmax], scheme="blues"),
            ),
            tooltip=[
                alt.Tooltip("dog_name:N", title="Dog"),
                alt.Tooltip("day:O", title="Day"),
                alt.Tooltip("distance_km:Q", title="Km", format=".1f"),
            ],
        )
        .properties(height=chart_height)
    )

    st.altair_chart(chart, use_container_width=True)
