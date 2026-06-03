"""Error explorer - drill into FAILED runs and their captured messages."""

from __future__ import annotations

import streamlit as st
from lib.config import INGEST_LOG_TABLE
from lib.session import get_session

st.set_page_config(page_title="Error explorer", page_icon="❄️", layout="wide")
session = get_session()

st.title("Error explorer")

failed = (
    session.sql(
        f"""
        SELECT RUN_ID, PROC_NAME, ERROR_MSG, STARTED_AT, ENDED_AT
        FROM {INGEST_LOG_TABLE}
        WHERE STATUS = 'FAILED'
        ORDER BY STARTED_AT DESC
        LIMIT 200
        """
    )
    .to_pandas()
)

if failed.empty:
    st.success("No failed runs recorded. The error path is clean.")
else:
    st.error(f"{len(failed)} failed run(s) recorded.")
    st.dataframe(failed, use_container_width=True, hide_index=True)
