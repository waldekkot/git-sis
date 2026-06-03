"""Integration tests for lib.ingest -- run against real Snowflake.

Requires SNOWFLAKE_DEFAULT_CONNECTION_NAME to be set; skipped automatically otherwise.
All tests use the temporary schema created by the test_schema fixture in conftest.py.

Run:
    SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/integration/ -v
"""

from __future__ import annotations

import importlib
import uuid

import lib.config as cfg
import pytest
from lib.ingest import get_kpis, get_run_history, run_ingestion


@pytest.fixture(autouse=True)
def _reload_config(test_schema):
    """Ensure lib.config sees the overridden GIT_SIS_SCHEMA before each test."""
    importlib.reload(cfg)


# ---------------------------------------------------------------------------
# run_ingestion -- success path
# ---------------------------------------------------------------------------


def test_success_path_returns_summary(sf_session, test_schema):
    run_id = str(uuid.uuid4())
    result = run_ingestion(sf_session, run_id, num_rows=25)

    assert result["run_id"] == run_id
    assert result["status"] == "SUCCESS"
    assert result["rows_loaded"] == 25


def test_success_path_lands_rows_in_orders(sf_session, test_schema):
    run_id = str(uuid.uuid4())
    run_ingestion(sf_session, run_id, num_rows=30)

    n = sf_session.sql(
        f"SELECT COUNT(*) C FROM {test_schema}.ORDERS WHERE RUN_ID = ?",
        params=[run_id],
    ).collect()[0]["C"]
    assert n == 30


def test_success_path_writes_success_log(sf_session, test_schema):
    run_id = str(uuid.uuid4())
    run_ingestion(sf_session, run_id, num_rows=15)

    row = sf_session.sql(
        f"SELECT STATUS, ROWS_LOADED FROM {test_schema}.INGEST_LOG WHERE RUN_ID = ?",
        params=[run_id],
    ).collect()[0]
    assert row["STATUS"] == "SUCCESS"
    assert row["ROWS_LOADED"] == 15


def test_success_path_orders_have_correct_regions(sf_session, test_schema):
    run_id = str(uuid.uuid4())
    run_ingestion(sf_session, run_id, num_rows=20)

    regions = {
        r["REGION"]
        for r in sf_session.sql(
            f"SELECT DISTINCT REGION FROM {test_schema}.ORDERS WHERE RUN_ID = ?",
            params=[run_id],
        ).collect()
    }
    assert regions.issubset({"US", "EU", "APAC", "LATAM"})


# ---------------------------------------------------------------------------
# run_ingestion -- failure path
# ---------------------------------------------------------------------------


def test_fail_path_reraises(sf_session, test_schema):
    with pytest.raises(ValueError, match="Injected failure"):
        run_ingestion(sf_session, str(uuid.uuid4()), fail=True)


def test_fail_path_writes_failed_log(sf_session, test_schema):
    run_id = str(uuid.uuid4())
    with pytest.raises(ValueError):
        run_ingestion(sf_session, run_id, fail=True)

    row = sf_session.sql(
        f"SELECT STATUS, ERROR_MSG FROM {test_schema}.INGEST_LOG WHERE RUN_ID = ?",
        params=[run_id],
    ).collect()[0]
    assert row["STATUS"] == "FAILED"
    assert "Injected failure" in row["ERROR_MSG"]


def test_fail_path_no_rows_in_orders(sf_session, test_schema):
    run_id = str(uuid.uuid4())
    with pytest.raises(ValueError):
        run_ingestion(sf_session, run_id, fail=True)

    n = sf_session.sql(
        f"SELECT COUNT(*) C FROM {test_schema}.ORDERS WHERE RUN_ID = ?",
        params=[run_id],
    ).collect()[0]["C"]
    assert n == 0


# ---------------------------------------------------------------------------
# get_kpis
# ---------------------------------------------------------------------------


def test_get_kpis_counts_both_statuses(sf_session, test_schema):
    # Ensure at least one success and one failure exist (may accumulate across tests)
    run_ingestion(sf_session, str(uuid.uuid4()), num_rows=5)
    with pytest.raises(ValueError):
        run_ingestion(sf_session, str(uuid.uuid4()), fail=True)

    kpis = get_kpis(sf_session)
    assert kpis["success_runs"] >= 1
    assert kpis["failed_runs"] >= 1
    assert kpis["total_runs"] == kpis["success_runs"] + kpis["failed_runs"]
    assert kpis["rows_loaded"] >= 5


# ---------------------------------------------------------------------------
# get_run_history
# ---------------------------------------------------------------------------


def test_get_run_history_sorted_most_recent_first(sf_session, test_schema):
    # Create two runs so we can check ordering
    run_ingestion(sf_session, str(uuid.uuid4()), num_rows=3)
    run_ingestion(sf_session, str(uuid.uuid4()), num_rows=3)

    df = get_run_history(sf_session, limit=10)
    assert "STATUS" in df.columns
    assert "STARTED_AT" in df.columns
    if len(df) > 1:
        assert df.iloc[0]["STARTED_AT"] >= df.iloc[1]["STARTED_AT"]


def test_get_run_history_respects_limit(sf_session, test_schema):
    df = get_run_history(sf_session, limit=2)
    assert len(df) <= 2
