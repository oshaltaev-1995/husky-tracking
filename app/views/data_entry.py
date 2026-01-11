from __future__ import annotations

from datetime import date as Date
from pathlib import Path

import pandas as pd
import streamlit as st

from app.services.export_excel import export_tracking_wide
from app.services.training_repo import upsert_training


def _show_flash() -> None:
    msg = st.session_state.pop("flash_message", None)
    kind = st.session_state.pop("flash_kind", None)  # "success" | "info" | "error"
    if not msg:
        return

    if kind == "success":
        st.success(msg)
    elif kind == "info":
        st.info(msg)
    elif kind == "error":
        st.error(msg)
    else:
        st.info(msg)


def render_data_entry(dff: pd.DataFrame, date_from: Date, date_to: Date) -> None:
    st.subheader("Data entry")
    st.caption("Add or correct a training record. Saved directly into the database.")

    # show message from last action (survives rerun)
    _show_flash()

    dogs = sorted(dff["dog_name"].unique().tolist())
    if not dogs:
        st.warning("No dogs found in the selected period. Expand date range or import data.")
        return

    # --- Form: add/update one record
    with st.form("add_training_form", clear_on_submit=False):
        c1, c2, c3 = st.columns([2, 1, 1])

        with c1:
            dog_name = st.selectbox("Dog", options=dogs)

        with c2:
            day = st.date_input("Date", value=date_to)

        with c3:
            km = st.number_input("Distance (km)", min_value=0.0, max_value=200.0, value=10.0, step=1.0)

        submitted = st.form_submit_button("Save to DB")

    if submitted:
        try:
            res = upsert_training(dog_name=dog_name, day=day, distance_km=km, source="ui")

            if res.action == "inserted":
                st.session_state["flash_kind"] = "success"
                st.session_state["flash_message"] = f"✅ Added: {dog_name} — {day} — {km:.1f} km"
            else:
                st.session_state["flash_kind"] = "info"
                st.session_state["flash_message"] = f"🔁 Updated: {dog_name} — {day} — {km:.1f} km"

            # clear cached DB reads & refresh app
            st.cache_data.clear()
            st.rerun()

        except Exception as e:
            st.session_state["flash_kind"] = "error"
            st.session_state["flash_message"] = f"❌ Failed to save: {e}"
            st.rerun()

    # --- Export block
    st.divider()
    st.subheader("Export to Excel")
    st.caption("Export the selected period to Excel (wide format: dogs x days).")

    st.info(
        f"Export uses the global date filters at the top of the page: "
        f"**{date_from} → {date_to}**"
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        export_clicked = st.button("Export selected period", key="export_selected_period")
    with c2:
        st.write("")  # spacer

    if export_clicked:
        out_dir = Path("data") / "exports"
        result = export_tracking_wide(dff=dff, date_from=date_from, date_to=date_to, out_dir=out_dir)

        st.success(f"✅ Exported: {result.path} (sheet: {result.sheet_name})")
        with open(result.path, "rb") as f:
            st.download_button(
                "Download Excel",
                data=f,
                file_name=result.path.name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_exported_excel",
            )
