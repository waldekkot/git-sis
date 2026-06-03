"""The local/SiS session seam.

This is the single place where running on a laptop differs from running inside
Streamlit-in-Snowflake. Everything above it (ingestion logic, UI) is identical
in both environments.

- In SiS (warehouse or container runtime): `get_active_session()` returns the
  app's embedded-identity Snowpark session. No secrets, no connection config.
- Locally (`streamlit run`): no active session exists, so we build one from a
  named CLI connection. We default to "default" and let
  SNOWFLAKE_DEFAULT_CONNECTION_NAME override it, e.g.:

      SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import os

import streamlit as st
from snowflake.snowpark import Session


@st.cache_resource(show_spinner="Connecting to Snowflake...")
def get_session() -> Session:
    """Return a Snowpark session, cached for the Streamlit app lifetime."""
    try:
        from snowflake.snowpark.context import get_active_session

        return get_active_session()  # SiS path
    except Exception:
        conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME") or "default"
        return Session.builder.config("connection_name", conn).create()  # local path
