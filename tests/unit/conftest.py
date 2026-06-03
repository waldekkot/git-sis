"""Shared fixtures and local-testing patches for unit tests.

Snowflake local testing framework reference:
  https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally

Design principles
-----------------
* Mock only what the local testing emulator cannot provide.
  - `uniform`, `round`: @snowflake.snowpark.mock.patch (preferred Snowflake API)
  - `call_function("UUID_STRING")`: unittest.mock (not in emulator; see uuid_patch)
  - Session backend: inject a real local testing session, never a MagicMock
* `seeded_session` provides empty ORDERS + INGEST_LOG tables per test.
  Every test that calls run_ingestion, get_kpis, or get_run_history needs this.
* `uuid_patch` is active for the duration of its fixture scope so all
  AppTest .run() calls within a test see the patch.
"""

from __future__ import annotations

import random as py_random
import uuid
from unittest.mock import patch as mock_patch

import pytest
from snowflake.snowpark import Session
from snowflake.snowpark.functions import lit
from snowflake.snowpark.functions import round as sf_round
from snowflake.snowpark.functions import uniform as sf_uniform
from snowflake.snowpark.mock import ColumnEmulator, ColumnType, patch
from snowflake.snowpark.types import (
    DoubleType,
    FloatType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from lib import config as _cfg

# ---------------------------------------------------------------------------
# Table schemas — match deploy/00_setup_env.sql exactly
# ---------------------------------------------------------------------------

LOG_SCHEMA = StructType(
    [
        StructField("RUN_ID", StringType()),
        StructField("PROC_NAME", StringType()),
        StructField("STATUS", StringType()),
        StructField("ROWS_LOADED", LongType()),
        StructField("ERROR_CODE", StringType()),
        StructField("ERROR_MSG", StringType()),
        StructField("STARTED_AT", TimestampType()),
        StructField("ENDED_AT", TimestampType()),
    ]
)

ORDERS_SCHEMA = StructType(
    [
        StructField("ORDER_ID", StringType()),
        StructField("RUN_ID", StringType()),
        StructField("CUSTOMER_ID", LongType()),
        StructField("AMOUNT", FloatType()),
        StructField("REGION", StringType()),
        StructField("ORDER_TS", TimestampType()),
    ]
)

# ---------------------------------------------------------------------------
# @snowflake.snowpark.mock.patch — functions not in the local testing emulator
# ---------------------------------------------------------------------------


@patch(sf_uniform)
def _mock_uniform(start, end, gen) -> ColumnEmulator:
    """UNIFORM(low, high, gen) -> random values in [low, high].

    From the Snowflake mock docs: LiteralType args are passed as plain Python
    values; ColumnOrName args arrive as ColumnEmulator objects.
    `lit(1)` and `lit(1000)` are literals; `random()` is a ColumnOrName.
    Integer bounds produce integer output; float bounds produce float output.
    """
    n = len(gen) if hasattr(gen, "__len__") else 1
    s = start.iloc[0] if hasattr(start, "iloc") else start
    e = end.iloc[0] if hasattr(end, "iloc") else end
    if isinstance(s, int) and isinstance(e, int):
        data = [py_random.randint(int(s), int(e)) for _ in range(n)]
        sf_type = ColumnType(LongType(), False)
    else:
        data = [py_random.uniform(float(s), float(e)) for _ in range(n)]
        sf_type = ColumnType(DoubleType(), False)
    result = ColumnEmulator(data=data)
    result.sf_type = sf_type
    return result


@patch(sf_round)
def _mock_round(value, scale=0) -> ColumnEmulator:
    """ROUND(value, scale) -> value rounded to `scale` decimal places."""
    scale_int = int(scale.iloc[0]) if hasattr(scale, "iloc") else int(scale)
    data = [round(float(v), scale_int) if v is not None else None for v in value]
    result = ColumnEmulator(data=data)
    result.sf_type = ColumnType(DoubleType(), False)
    return result


# ---------------------------------------------------------------------------
# pytest options
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --snowflake-session option per Snowflake testing docs convention."""
    parser.addoption(
        "--snowflake-session",
        action="store",
        default="local",
        help="'local' (default) uses the in-process emulator; 'live' connects to Snowflake.",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_session(request) -> Session:
    """Fresh Snowpark local testing session with empty ORDERS + INGEST_LOG tables.

    Function-scoped: each test gets clean tables, preventing cross-test interference.

    When --snowflake-session=live (with SNOWFLAKE_DEFAULT_CONNECTION_NAME set),
    creates a temporary schema in real Snowflake instead.  Useful for cross-
    validating that local testing results match production behaviour.
    """
    mode = request.config.getoption("--snowflake-session", default="local")

    if mode == "local":
        sess = Session.builder.config("local_testing", True).create()
        sess.create_dataframe([], LOG_SCHEMA).write.save_as_table(_cfg.INGEST_LOG_TABLE)
        sess.create_dataframe([], ORDERS_SCHEMA).write.save_as_table(_cfg.ORDERS_TABLE)
        yield sess
        sess.close()
    else:
        import importlib
        import os

        conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", "default")
        sess = Session.builder.config("connection_name", conn).create()

        import uuid as _uuid

        schema_fqn = f"SNOWFLAKE_LEARNING_DB.GIT_SIS_TEST_{_uuid.uuid4().hex[:8].upper()}"
        sess.sql(f"CREATE SCHEMA IF NOT EXISTS {schema_fqn}").collect()
        sess.sql(
            f"""CREATE OR ALTER TABLE {schema_fqn}.ORDERS (
                ORDER_ID STRING, RUN_ID STRING, CUSTOMER_ID NUMBER,
                AMOUNT FLOAT, REGION STRING, ORDER_TS TIMESTAMP_LTZ)"""
        ).collect()
        sess.sql(
            f"""CREATE OR ALTER TABLE {schema_fqn}.INGEST_LOG (
                RUN_ID STRING, PROC_NAME STRING, STATUS STRING, ROWS_LOADED NUMBER,
                ERROR_CODE STRING, ERROR_MSG STRING,
                STARTED_AT TIMESTAMP_LTZ, ENDED_AT TIMESTAMP_LTZ)"""
        ).collect()

        os.environ["GIT_SIS_SCHEMA"] = schema_fqn
        importlib.reload(importlib.import_module("lib.config"))

        yield sess

        sess.sql(f"DROP SCHEMA IF EXISTS {schema_fqn} CASCADE").collect()
        del os.environ["GIT_SIS_SCHEMA"]
        sess.close()


@pytest.fixture()
def uuid_patch():
    """Patch call_function('UUID_STRING') for the Snowpark local testing emulator.

    UUID_STRING is a Snowflake built-in not implemented in the local emulator.
    This is the only unittest.mock patch needed in unit tests — a pure emulator
    limitation, not business logic.

    Active for the entire test function (including all AppTest .run() calls).
    """
    with mock_patch(
        "lib.ingest.call_function",
        side_effect=lambda _name: lit(str(uuid.uuid4())),
    ):
        yield


# ---------------------------------------------------------------------------
# Legacy alias — keeps test_ingest.py working without changes during migration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def local_session(request) -> Session:
    """Module-scoped alias for backwards compatibility.

    Prefer `seeded_session` (function-scoped) for new tests.
    """
    mode = request.config.getoption("--snowflake-session", default="local")
    if mode == "local":
        sess = Session.builder.config("local_testing", True).create()
    else:
        import os

        conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", "default")
        sess = Session.builder.config("connection_name", conn).create()
    yield sess
    sess.close()
