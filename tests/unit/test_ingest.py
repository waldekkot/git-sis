"""Unit tests for lib.ingest using Snowflake's local testing framework.

Uses Session.builder.config("local_testing", True) for an in-process Snowflake
emulator — no credentials, no network, no Snowflake account required.

Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally

Key patterns applied:
- session.sql() is NOT supported in local testing; ingest.py was refactored to
  use the DataFrame API exclusively so tests run unmodified.
- call_function("UUID_STRING") is not implemented in the local emulator — we
  patch lib.ingest.call_function so it returns lit(<uuid>) per call.
- Each test gets a fresh session (function scope) for full isolation.
- Tables are pre-created with the correct schema via the `tables` fixture so
  _log_start (append) and _log_finish (update) have a table to work with.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch as mock_patch

import pandas as pd
import pytest
from lib import config as _cfg
from lib.ingest import PROC_NAME, _synthetic_orders, get_kpis, get_run_history, run_ingestion
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col, lit
from snowflake.snowpark.types import (
    FloatType,
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ORDERS_SCHEMA = StructType(
    [
        StructField("ORDER_ID", StringType()),
        StructField("RUN_ID", StringType()),
        StructField("CUSTOMER_ID", LongType()),
        StructField("AMOUNT", FloatType()),
        StructField("REGION", StringType()),
        StructField("ORDER_TS", TimestampType()),
    ]
)

_LOG_SCHEMA = StructType(
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


@pytest.fixture()
def session():
    """Fresh in-process Snowflake emulator session per test — no credentials needed.

    Per Snowflake docs, use Session.builder.config("local_testing", True).create()
    to get a session backed by the local testing framework.
    """
    sess = Session.builder.config("local_testing", True).create()
    # Pre-create empty tables so _log_finish (update) and read helpers can find them
    sess.create_dataframe([], _ORDERS_SCHEMA).write.save_as_table(_cfg.ORDERS_TABLE)
    sess.create_dataframe([], _LOG_SCHEMA).write.save_as_table(_cfg.INGEST_LOG_TABLE)
    yield sess
    sess.close()


def _uuid_patch():
    """Patch context: replaces call_function('UUID_STRING') with lit(<uuid>).

    UUID_STRING is a Snowflake built-in that is not implemented in the local
    testing emulator.  We return a Column literal so the DataFrame plan is valid
    (rows get unique IDs only when lit is called per select; acceptable for tests).
    """
    return mock_patch(
        "lib.ingest.call_function",
        side_effect=lambda name: lit(str(uuid.uuid4())),
    )


# ---------------------------------------------------------------------------
# run_ingestion — success path: verify data flow end-to-end
# ---------------------------------------------------------------------------


def test_run_ingestion_success_returns_summary(session):
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        result = run_ingestion(session, run_id, num_rows=5)

    assert result == {"run_id": run_id, "status": "SUCCESS", "rows_loaded": 5}


def test_run_ingestion_success_lands_rows_in_orders(session):
    """Rows are written to ORDERS with the correct RUN_ID stamp."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        run_ingestion(session, run_id, num_rows=7)

    rows = session.table(_cfg.ORDERS_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    assert len(rows) == 7


def test_run_ingestion_success_writes_success_log(session):
    """INGEST_LOG shows STATUS=SUCCESS and correct ROWS_LOADED."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        run_ingestion(session, run_id, num_rows=3)

    log = session.table(_cfg.INGEST_LOG_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    assert len(log) == 1
    assert log[0]["STATUS"] == "SUCCESS"
    assert log[0]["ROWS_LOADED"] == 3
    assert log[0]["PROC_NAME"] == PROC_NAME


def test_run_ingestion_success_orders_have_valid_regions(session):
    """REGION column contains only the four expected values."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        run_ingestion(session, run_id, num_rows=40)

    rows = session.table(_cfg.ORDERS_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    regions = {r["REGION"] for r in rows}
    assert regions <= {"US", "EU", "APAC", "LATAM"}


# ---------------------------------------------------------------------------
# run_ingestion — failure path
# ---------------------------------------------------------------------------


def test_run_ingestion_fail_reraises(session):
    with pytest.raises(ValueError, match="Injected failure"):
        run_ingestion(session, str(uuid.uuid4()), fail=True)


def test_run_ingestion_fail_writes_failed_log(session):
    """FAILED run creates a log entry with STATUS=FAILED and captured error message."""
    run_id = str(uuid.uuid4())
    with pytest.raises(ValueError):
        run_ingestion(session, run_id, fail=True)

    log = session.table(_cfg.INGEST_LOG_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    assert len(log) == 1
    assert log[0]["STATUS"] == "FAILED"
    assert "Injected failure" in (log[0]["ERROR_MSG"] or "")


def test_run_ingestion_fail_no_rows_in_orders(session):
    """A failed run must not write any rows to ORDERS."""
    run_id = str(uuid.uuid4())
    with pytest.raises(ValueError):
        run_ingestion(session, run_id, fail=True)

    count = session.table(_cfg.ORDERS_TABLE).filter(col("RUN_ID") == lit(run_id)).count()
    assert count == 0


# ---------------------------------------------------------------------------
# _synthetic_orders — DataFrame plan: verify structure and content
# ---------------------------------------------------------------------------


def test_synthetic_orders_produces_correct_row_count(session):
    """_synthetic_orders yields exactly num_rows rows when collected."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        df = _synthetic_orders(session, run_id, num_rows=4)
        rows = df.collect()
    assert len(rows) == 4


def test_synthetic_orders_stamps_run_id(session):
    """Every generated row carries the correct RUN_ID value."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        rows = _synthetic_orders(session, run_id, num_rows=3).collect()
    assert all(r["RUN_ID"] == run_id for r in rows)


def test_synthetic_orders_regions_from_expected_set(session):
    """REGION is always one of US / EU / APAC / LATAM (no nulls, no typos)."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        rows = _synthetic_orders(session, run_id, num_rows=40).collect()
    regions = {r["REGION"] for r in rows}
    assert regions <= {"US", "EU", "APAC", "LATAM"}
    assert len(regions) > 1, "Expected multiple distinct regions across 40 rows"


# ---------------------------------------------------------------------------
# get_run_history
# ---------------------------------------------------------------------------


def test_get_run_history_returns_empty_dataframe_before_any_runs(session):
    """Before any ingestion, get_run_history returns an empty DataFrame."""
    result = get_run_history(session, limit=10)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_get_run_history_shows_completed_run(session):
    """A completed run appears in the history with the correct RUN_ID."""
    run_id = str(uuid.uuid4())
    with _uuid_patch():
        run_ingestion(session, run_id, num_rows=2)

    history = get_run_history(session, limit=5)
    assert run_id in history["RUN_ID"].values


def test_get_run_history_respects_limit(session):
    """Only 'limit' most-recent rows are returned."""
    with _uuid_patch():
        for _ in range(5):
            run_ingestion(session, str(uuid.uuid4()), num_rows=1)

    history = get_run_history(session, limit=3)
    assert len(history) == 3


# ---------------------------------------------------------------------------
# get_kpis
# ---------------------------------------------------------------------------


def test_get_kpis_returns_all_keys(session):
    kpis = get_kpis(session)
    assert set(kpis.keys()) == {"total_runs", "failed_runs", "success_runs", "rows_loaded"}


def test_get_kpis_zero_before_any_runs(session):
    kpis = get_kpis(session)
    assert kpis["total_runs"] == 0
    assert kpis["rows_loaded"] == 0


def test_get_kpis_counts_both_statuses(session):
    """Two runs (one success, one fail) are reflected accurately in KPIs."""
    with _uuid_patch():
        run_ingestion(session, str(uuid.uuid4()), num_rows=10)
    with pytest.raises(ValueError):
        run_ingestion(session, str(uuid.uuid4()), fail=True)

    kpis = get_kpis(session)
    assert kpis["total_runs"] == 2
    assert kpis["success_runs"] == 1
    assert kpis["failed_runs"] == 1
    assert kpis["rows_loaded"] == 10
