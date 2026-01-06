from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app.db import engine

st.set_page_config(page_title="Husky Tracking (Demo)", layout="wide")
st.title("Husky Tracking — Demo")


@st.cache_data
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


df = load_data()
if df.empty:
    st.warning("No data in database yet. Run import first.")
    st.stop()

# --- Date filters
min_date = df["date"].min().date()
max_date = df["date"].max().date()

col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input(
        "From",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )
with col2:
    date_to = st.date_input(
        "To",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

# Ensure correct order (if user picks backwards)
if date_from > date_to:
    date_from, date_to = date_to, date_from

mask = (df["date"].dt.date >= date_from) & (df["date"].dt.date <= date_to)
dff = df.loc[mask].copy()

# --- KPIs (same row)
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Dogs", int(dff["dog_name"].nunique()))
with k2:
    st.metric("Days", int(dff["date"].dt.date.nunique()))
with k3:
    st.metric("Total km (selected period)", float(dff["distance_km"].sum()))

st.divider()

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

# --- Daily sum (robust: column name is guaranteed)
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
