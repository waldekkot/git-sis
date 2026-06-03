"""Integration test fixtures -- requires a real Snowflake connection.

All tests in this package are skipped automatically if the environment variable
SNOWFLAKE_DEFAULT_CONNECTION_NAME is not set.

Run manually:
    SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/integration/ -v

A temporary test schema (GIT_SIS_TEST_<8-char uuid>) is created at session start
and dropped at session end, so integration tests never touch production data.
"""
from __future__ import annotations

import os
import uuid

import pytest
from snowflake.snowpark import Session


_CONN = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME")


@pytest.fixture(scope="session")
def sf_session():
    if not _CONN:
        pytest.skip(
            "SNOWFLAKE_DEFAULT_CONNECTION_NAME not set -- skipping integration tests. "
            "Set it to a CLI connection name (e.g. 'oregon-sedemo') and re-run."
        )
    sess = Session.builder.config("connection_name", _CONN).create()
    yield sess
    sess.close()


@pytest.fixture(scope="session")
def test_schema(sf_session) -> str:
    """Create a dedicated temporary schema for this test run and tear it down afterward."""
    schema_fqn = f"SNOWFLAKE_LEARNING_DB.GIT_SIS_TEST_{uuid.uuid4().hex[:8].upper()}"

    sf_session.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_fqn}").collect()
    sf_session.sql(
        f"""
        CREATE OR ALTER TABLE {schema_fqn}.ORDERS (
            ORDER_ID    STRING,
            RUN_ID      STRING,
            CUSTOMER_ID NUMBER,
            AMOUNT      FLOAT,
            REGION      STRING,
            ORDER_TS    TIMESTAMP_LTZ
        )
        """
    ).collect()
    sf_session.sql(
        f"""
        CREATE OR ALTER TABLE {schema_fqn}.INGEST_LOG (
            RUN_ID      STRING,
            PROC_NAME   STRING,
            STATUS      STRING,
            ROWS_LOADED NUMBER,
            ERROR_CODE  STRING,
            ERROR_MSG   STRING,
            STARTED_AT  TIMESTAMP_LTZ,
            ENDED_AT    TIMESTAMP_LTZ
        )
        """
    ).collect()

    # Override the schema used by lib.config for this test session
    os.environ["GIT_SIS_SCHEMA"] = schema_fqn

    # Reload config so the new env var takes effect
    import importlib
    import lib.config as cfg
    importlib.reload(cfg)

    yield schema_fqn

    # Teardown
    sf_session.sql(f"DROP SCHEMA IF EXISTS {schema_fqn} CASCADE").collect()
    del os.environ["GIT_SIS_SCHEMA"]
