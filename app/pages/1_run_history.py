"""Run history - full, filterable view of INGEST_LOG."""

from __future__ import annotations

import streamlit as st
from lib.ingest import get_run_history
from lib.session import get_session

st.set_page_config(page_title="Run history", page_icon="❄️", layout="wide")
session = get_session()

st.title("Run history")

status = st.multiselect(
    "Filter by status",
    options=["SUCCESS", "FAILED", "RUNNING"],
    default=["SUCCESS", "FAILED", "RUNNING"],
)
limit = st.slider("Max rows", min_value=10, max_value=1000, value=200, step=10)

df = get_run_history(session, limit=limit)
if status and "STATUS" in df.columns:
    df = df[df["STATUS"].isin(status)]

st.dataframe(df, use_container_width=True, hide_index=True)
st.caption(f"{len(df)} runs shown.")
