"""Integration test fixtures -- requires a real Snowflake connection.

All tests in this package are skipped automatically if the environment variable
SNOWFLAKE_DEFAULT_CONNECTION_NAME is not set.

Run manually:
    SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/integration/ -v

Parallelism
-----------
test_schema is function-scoped: each test gets its own disposable
GIT_SIS_TEST_<uuid> schema.  Combined with pytest-xdist (-n auto), all 10
tests run in parallel across separate worker processes, each with its own
Snowflake session.  Schemas never collide; no shared mutable state.

Expected wall time:
    Serial (-n 1):  ~60 s
    Parallel (-n 5): ~12 s  (limited by Snowflake DDL round-trip, not CPU)
"""

from __future__ import annotations

import importlib
import os
import uuid

import pytest
from snowflake.snowpark import Session

_CONN = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME")


@pytest.fixture(scope="session")
def sf_session():
    """One Snowflake session per xdist worker process.

    Session-scoped so we don't open/close a connection for every test —
    the per-test cost is the schema create/drop, not the connection itself.
    """
    if not _CONN:
        pytest.skip(
            "SNOWFLAKE_DEFAULT_CONNECTION_NAME not set -- skipping integration tests. "
            "Set it to a CLI connection name (e.g. 'oregon-sedemo') and re-run."
        )
    sess = Session.builder.config("connection_name", _CONN).create()
    yield sess
    sess.close()


@pytest.fixture()
def test_schema(sf_session) -> str:
    """Disposable schema per test — created before the test, dropped after.

    Function-scoped so that:
    - each test starts with empty, isolated tables (no cross-test state bleed)
    - xdist workers can run tests in parallel without schema collisions

    The schema FQN is pushed into GIT_SIS_SCHEMA so lib.config picks it up
    at import time (and via _reload_config autouse below).
    """
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

    os.environ["GIT_SIS_SCHEMA"] = schema_fqn

    import lib.config as cfg

    importlib.reload(cfg)

    yield schema_fqn

    sf_session.sql(f"DROP SCHEMA IF EXISTS {schema_fqn} CASCADE").collect()
    del os.environ["GIT_SIS_SCHEMA"]
