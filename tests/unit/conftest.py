"""Shared fixtures and local-testing patches for unit tests.

Snowflake local testing framework reference:
  https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally

Design principles
-----------------
* Mock only what the local testing emulator cannot provide.
  - `uniform`, `round`: @snowflake.snowpark.mock.patch (preferred Snowflake API)
  - `call_function("UUID_STRING")`: unittest.mock (not in emulator; see uuid_patch)
  - Session backend: inject a real session (emulator or live), never a MagicMock
* `_module_session` creates ONE session per test module in both modes:
  - local : Snowpark local-testing emulator   (~30 ms, zero credentials)
  - live  : real Snowflake with a disposable  (~2 s,  temp schema)
            GIT_SIS_TEST_<uuid> schema
  This avoids 44 × session-create overhead (the dominant cost at 46 tests).
* `seeded_session` truncates ORDERS + INGEST_LOG with .delete() (~2 ms local,
  ~100 ms live) before each test, providing clean isolated state without a new
  connection.
* `uuid_patch` is active for the duration of its fixture scope so all
  AppTest .run() calls within a test see the patch.
"""

from __future__ import annotations

import importlib
import os
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


@pytest.fixture(scope="module")
def _module_session(request) -> Session:
    """One session per test module — emulator in local mode, real Snowflake in live mode.

    local mode
        Creates a Snowpark local-testing session with empty ORDERS + INGEST_LOG
        tables (~30 ms).  Zero credentials, zero network.

    live mode
        Creates a real Snowflake session and a disposable GIT_SIS_TEST_<uuid>
        schema (~2 s).  The schema FQN is written to GIT_SIS_SCHEMA so that
        lib.config picks it up for this worker process.  Schema is dropped in
        teardown.

    Why module scope?
        Session creation costs ~30 ms (local) or ~2 s (live).  With 46 tests
        this would add ~1.4 s (local) or ~90 s (live) of pure setup overhead.
        One session per module (2 modules with seeded_session tests) costs
        ~60 ms / ~4 s — a 20–45× reduction.

    Compatible with pytest-xdist --dist=loadfile: all tests from the same file
    run on the same worker, so this module session is never shared across
    workers.
    """
    mode = request.config.getoption("--snowflake-session", default="local")

    if mode == "local":
        sess = Session.builder.config("local_testing", True).create()
        sess.create_dataframe([], LOG_SCHEMA).write.save_as_table(_cfg.INGEST_LOG_TABLE)
        sess.create_dataframe([], ORDERS_SCHEMA).write.save_as_table(_cfg.ORDERS_TABLE)
        yield sess
        sess.close()

    else:  # live
        import uuid as _uuid

        conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", "default")
        sess = Session.builder.config("connection_name", conn).create()

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
def seeded_session(request, _module_session) -> Session:  # noqa: ARG001
    """Clean ORDERS + INGEST_LOG tables before each test.

    Reuses the module-scoped session — no new connection per test.
    Truncates via DataFrame.delete() (~2 ms local, ~100 ms live).
    In live mode, reloads lib.config to ensure the per-module schema FQN
    set by _module_session is reflected in _cfg.ORDERS_TABLE etc.
    """
    mode = request.config.getoption("--snowflake-session", default="local")
    if mode != "local":
        # Re-sync config in case another fixture temporarily changed it.
        importlib.reload(importlib.import_module("lib.config"))

    _module_session.table(_cfg.ORDERS_TABLE).delete()
    _module_session.table(_cfg.INGEST_LOG_TABLE).delete()
    yield _module_session
    # No teardown: next test's setup truncates again.


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
# Legacy alias — kept for backwards compatibility; prefer seeded_session
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
        conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", "default")
        sess = Session.builder.config("connection_name", conn).create()
    yield sess
    sess.close()
