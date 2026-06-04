"""Ingestion Ops Console - Streamlit-in-Snowflake entry point.

Monitors the synthetic-orders ingestion pipeline: headline KPIs, run history,
and an operator control to trigger a run (or deliberately fail one to show the
error path). Runs unchanged locally and in SiS via the lib.session seam.
"""

from __future__ import annotations

import uuid

import streamlit as st
from lib.ingest import get_kpis, get_run_history, purge_orders, run_ingestion
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
    st.dataframe(get_run_history(session, limit=100), width="stretch", hide_index=True)
except Exception as exc:  # noqa: BLE001
    st.warning(f"Could not load run history yet: {exc}")
    st.info("If this is the first run, ensure deploy/00_setup_env.sql has created the tables.")

# --- Danger Zone -------------------------------------------------------------


@st.dialog("Confirm purge", icon="⚠️")
def _confirm_purge_dialog() -> None:
    """Modal confirmation before irreversible ORDERS deletion.

    @st.dialog is a fragment: only this function reruns on widget interaction,
    not the whole page.  Ref: https://docs.streamlit.io/develop/api-reference/execution-flow/st.dialog
    """
    st.warning("This will permanently delete **all rows** from the ORDERS table.")
    st.caption("This action cannot be undone. The deletion will be logged to INGEST_LOG.")
    col1, col2 = st.columns(2)
    if col1.button("Confirm purge", type="primary", use_container_width=True):
        try:
            with st.spinner("Purging ORDERS..."):
                rows_deleted = purge_orders(session)
            st.session_state["_purge_result"] = rows_deleted
        except Exception as exc:  # noqa: BLE001
            st.session_state["_purge_error"] = str(exc)
        st.rerun()
    if col2.button("Cancel", use_container_width=True):
        st.rerun()


with st.expander("⚠️ Danger Zone", expanded=False):
    st.caption("Irreversible operations — use with care.")
    if st.button("🗑 Purge orders", type="secondary", help="Delete all rows from the ORDERS table"):
        _confirm_purge_dialog()

# Surface purge result / error after the dialog closes and the app reruns.
# No st.rerun() here — KPIs are already refreshed by the dialog's own rerun.
# The message persists until the next user interaction (intentional: informs the operator).
if "_purge_result" in st.session_state:
    rows = st.session_state.pop("_purge_result")
    st.success(f"ORDERS purged — {rows:,} rows deleted.")

if "_purge_error" in st.session_state:
    err = st.session_state.pop("_purge_error")
    st.error(f"Purge failed: {err}")
