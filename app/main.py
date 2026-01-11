from __future__ import annotations

import streamlit as st

from app.data_access.repo import load_data
from app.views.overview import render_overview
from app.views.heatmap import render_heatmap
from app.views.red_flags import render_red_flags
from app.views.dog_profile import render_dog_profile
from app.views.data_entry import render_data_entry
from app.views.team_suggestions import render_team_suggestions


st.set_page_config(page_title="Husky Tracking (Demo)", layout="wide")
st.title("Husky Tracking — Demo")

df = load_data()
if df.empty:
    st.warning("No data in database yet. Run import first.")
    st.stop()

# --- Date filters (global)
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

# Ensure correct order
if date_from > date_to:
    date_from, date_to = date_to, date_from

mask = (df["date"].dt.date >= date_from) & (df["date"].dt.date <= date_to)
dff = df.loc[mask].copy()

# --- KPIs (global)
k1, k2, k3 = st.columns(3)
with k1:
    st.metric("Dogs", int(dff["dog_name"].nunique()))
with k2:
    st.metric("Days", int(dff["date"].dt.date.nunique()))
with k3:
    st.metric("Total km (selected period)", float(dff["distance_km"].sum()))

st.divider()

tabs = st.tabs(["Overview", "Heatmap", "Dog profile", "Red flags", "Data entry", "Team suggestions"])

with tabs[0]:
    render_overview(dff)

with tabs[1]:
    render_heatmap(dff)

with tabs[2]:
    render_dog_profile(dff)

with tabs[3]:
    render_red_flags(dff)

with tabs[4]:
    # Data entry writes to DB, and can export selected period to Excel
    render_data_entry(dff=dff, date_from=date_from, date_to=date_to)

with tabs[5]:
    render_team_suggestions(dff)
