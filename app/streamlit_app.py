"""Ingestion Ops Console - Streamlit-in-Snowflake entry point.

Monitors the synthetic-orders ingestion pipeline: headline KPIs, run history,
and an operator control to trigger a run (or deliberately fail one to show the
error path). Runs unchanged locally and in SiS via the lib.session seam.
"""

from __future__ import annotations

import uuid

import streamlit as st
from lib.ingest import get_kpis, get_run_history, run_ingestion
from lib.session import get_session

st.set_page_config(page_title="Ingestion Ops Console", page_icon="❄️", layout="wide")

session = get_session()

st.title("Ingestion Ops Console")
st.caption("Synthetic-orders ingestion with structured logging and error handling.")

# --- Operator controls -------------------------------------------------------
with st.container(border=True):
    st.subheader("Trigger a run")
    c1, c2, c3 = st.columns([1, 1, 2])
    num_rows = c1.number_input(
        "Rows to ingest", min_value=1, max_value=100_000, value=500, step=100
    )
    force_fail = c2.toggle("Force a failure", value=False, help="Exercise the error path")
    if c3.button("Run ingestion", type="primary", use_container_width=True):
        run_id = str(uuid.uuid4())
        try:
            with st.spinner(f"Running ingestion {run_id}..."):
                result = run_ingestion(session, run_id, num_rows=int(num_rows), fail=force_fail)
            st.success(f"Run {run_id} succeeded - {result['rows_loaded']} rows loaded.")
        except Exception as exc:  # noqa: BLE001 - surface, don't crash
            st.error(f"Run {run_id} FAILED and was logged: {exc}")
        st.rerun()

# --- KPIs --------------------------------------------------------------------
try:
    kpis = get_kpis(session)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total runs", f"{kpis['total_runs']:,}")
    m2.metric("Succeeded", f"{kpis['success_runs']:,}")
    m3.metric("Failed", f"{kpis['failed_runs']:,}")
    m4.metric("Rows loaded", f"{kpis['rows_loaded']:,}")

    st.subheader("Recent runs")
    st.dataframe(get_run_history(session, limit=100), use_container_width=True, hide_index=True)
except Exception as exc:  # noqa: BLE001
    st.warning(f"Could not load run history yet: {exc}")
    st.info("If this is the first run, ensure deploy/00_setup_env.sql has created the tables.")
