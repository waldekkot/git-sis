"""Unit tests for lib.ingest using Snowflake's local testing framework.

Uses Session.builder.config("local_testing", True) for an in-process Snowflake
emulator — no credentials, no network, no Snowflake account required.

Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally

Key patterns applied:
- session.sql() is NOT supported in local testing; ingest.py uses the DataFrame
  API exclusively so all operations run natively in the emulator.
- call_function("UUID_STRING") is not in the emulator — provided via the
  `uuid_patch` fixture (defined in conftest.py; active as a fixture parameter).
- `seeded_session` (conftest.py): function-scoped, gives each test empty tables.
- No other mocks — all DataFrame operations run against the real emulator.
"""

from __future__ import annotations

import uuid

import pandas as pd
import pytest
from lib.ingest import PROC_NAME, _synthetic_orders, get_kpis, get_run_history, run_ingestion
from snowflake.snowpark.functions import col, lit

from lib import config as _cfg

# ---------------------------------------------------------------------------
# run_ingestion — success path: verify data flow end-to-end
# ---------------------------------------------------------------------------


def test_run_ingestion_success_returns_summary(seeded_session, uuid_patch):  # noqa: ARG001
    run_id = str(uuid.uuid4())
    result = run_ingestion(seeded_session, run_id, num_rows=5)

    assert result == {"run_id": run_id, "status": "SUCCESS", "rows_loaded": 5}


def test_run_ingestion_success_lands_rows_in_orders(seeded_session, uuid_patch):  # noqa: ARG001
    """Rows are written to ORDERS with the correct RUN_ID stamp."""
    run_id = str(uuid.uuid4())
    run_ingestion(seeded_session, run_id, num_rows=7)

    rows = seeded_session.table(_cfg.ORDERS_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    assert len(rows) == 7


def test_run_ingestion_success_writes_success_log(seeded_session, uuid_patch):  # noqa: ARG001
    """INGEST_LOG shows STATUS=SUCCESS and correct ROWS_LOADED."""
    run_id = str(uuid.uuid4())
    run_ingestion(seeded_session, run_id, num_rows=3)

    log = seeded_session.table(_cfg.INGEST_LOG_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    assert len(log) == 1
    assert log[0]["STATUS"] == "SUCCESS"
    assert log[0]["ROWS_LOADED"] == 3
    assert log[0]["PROC_NAME"] == PROC_NAME


def test_run_ingestion_success_orders_have_valid_regions(seeded_session, uuid_patch):  # noqa: ARG001
    """REGION column contains only the four expected values."""
    run_id = str(uuid.uuid4())
    run_ingestion(seeded_session, run_id, num_rows=40)

    rows = seeded_session.table(_cfg.ORDERS_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    regions = {r["REGION"] for r in rows}
    assert regions <= {"US", "EU", "APAC", "LATAM"}


# ---------------------------------------------------------------------------
# run_ingestion — failure path
# ---------------------------------------------------------------------------


def test_run_ingestion_fail_reraises(seeded_session):
    with pytest.raises(ValueError, match="Injected failure"):
        run_ingestion(seeded_session, str(uuid.uuid4()), fail=True)


def test_run_ingestion_fail_writes_failed_log(seeded_session):
    """FAILED run creates a log entry with STATUS=FAILED and captured error message."""
    run_id = str(uuid.uuid4())
    with pytest.raises(ValueError):
        run_ingestion(seeded_session, run_id, fail=True)

    log = seeded_session.table(_cfg.INGEST_LOG_TABLE).filter(col("RUN_ID") == lit(run_id)).collect()
    assert len(log) == 1
    assert log[0]["STATUS"] == "FAILED"
    assert "Injected failure" in (log[0]["ERROR_MSG"] or "")


def test_run_ingestion_fail_no_rows_in_orders(seeded_session):
    """A failed run must not write any rows to ORDERS."""
    run_id = str(uuid.uuid4())
    with pytest.raises(ValueError):
        run_ingestion(seeded_session, run_id, fail=True)

    count = seeded_session.table(_cfg.ORDERS_TABLE).filter(col("RUN_ID") == lit(run_id)).count()
    assert count == 0


# ---------------------------------------------------------------------------
# _synthetic_orders — DataFrame plan: verify structure and content
# ---------------------------------------------------------------------------


def test_synthetic_orders_produces_correct_row_count(seeded_session, uuid_patch):  # noqa: ARG001
    """_synthetic_orders yields exactly num_rows rows when collected."""
    run_id = str(uuid.uuid4())
    df = _synthetic_orders(seeded_session, run_id, num_rows=4)
    rows = df.collect()
    assert len(rows) == 4


def test_synthetic_orders_stamps_run_id(seeded_session, uuid_patch):  # noqa: ARG001
    """Every generated row carries the correct RUN_ID value."""
    run_id = str(uuid.uuid4())
    rows = _synthetic_orders(seeded_session, run_id, num_rows=3).collect()
    assert all(r["RUN_ID"] == run_id for r in rows)


def test_synthetic_orders_regions_from_expected_set(seeded_session, uuid_patch):  # noqa: ARG001
    """REGION is always one of US / EU / APAC / LATAM (no nulls, no typos)."""
    run_id = str(uuid.uuid4())
    rows = _synthetic_orders(seeded_session, run_id, num_rows=40).collect()
    regions = {r["REGION"] for r in rows}
    assert regions <= {"US", "EU", "APAC", "LATAM"}
    assert len(regions) > 1, "Expected multiple distinct regions across 40 rows"


# ---------------------------------------------------------------------------
# get_run_history
# ---------------------------------------------------------------------------


def test_get_run_history_returns_empty_dataframe_before_any_runs(seeded_session):
    """Before any ingestion, get_run_history returns an empty DataFrame."""
    result = get_run_history(seeded_session, limit=10)
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_get_run_history_shows_completed_run(seeded_session, uuid_patch):  # noqa: ARG001
    """A completed run appears in the history with the correct RUN_ID."""
    run_id = str(uuid.uuid4())
    run_ingestion(seeded_session, run_id, num_rows=2)

    history = get_run_history(seeded_session, limit=5)
    assert run_id in history["RUN_ID"].values


def test_get_run_history_respects_limit(seeded_session, uuid_patch):  # noqa: ARG001
    """Only 'limit' most-recent rows are returned."""
    for _ in range(5):
        run_ingestion(seeded_session, str(uuid.uuid4()), num_rows=1)

    history = get_run_history(seeded_session, limit=3)
    assert len(history) == 3


# ---------------------------------------------------------------------------
# get_kpis
# ---------------------------------------------------------------------------


def test_get_kpis_returns_all_keys(seeded_session):
    kpis = get_kpis(seeded_session)
    assert set(kpis.keys()) == {"total_runs", "failed_runs", "success_runs", "rows_loaded"}


def test_get_kpis_zero_before_any_runs(seeded_session):
    kpis = get_kpis(seeded_session)
    assert kpis["total_runs"] == 0
    assert kpis["rows_loaded"] == 0


def test_get_kpis_counts_both_statuses(seeded_session, uuid_patch):  # noqa: ARG001
    """Two runs (one success, one fail) are reflected accurately in KPIs."""
    run_ingestion(seeded_session, str(uuid.uuid4()), num_rows=10)
    with pytest.raises(ValueError):
        run_ingestion(seeded_session, str(uuid.uuid4()), fail=True)

    kpis = get_kpis(seeded_session)
    assert kpis["total_runs"] == 2
    assert kpis["success_runs"] == 1
    assert kpis["failed_runs"] == 1
    assert kpis["rows_loaded"] == 10
