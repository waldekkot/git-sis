"""Unit tests for lib.ingest -- all Snowflake calls are mocked.

Design notes:
- session.sql() and session.table().update() don't work in local_testing mode,
  so we use MagicMock() for the session in orchestration tests.
- _synthetic_orders builds a Snowpark lazy plan that calls call_function("UUID_STRING")
  which can't execute in local_testing. It is covered in integration tests.
  Here we only verify the function is importable and returns a DF-like object
  via a mock session.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from snowflake.snowpark.functions import lit as real_lit

from lib.ingest import PROC_NAME, get_kpis, get_run_history, run_ingestion


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """A MagicMock that satisfies the Snowpark Session interface used by ingest.py."""
    sess = MagicMock()
    # session.sql(...).collect() -> []
    sess.sql.return_value.collect.return_value = []
    # session.table(...).update(...) -> MagicMock()
    # session.table(...).sort(...).limit(...).to_pandas() -> empty DataFrame
    sess.table.return_value.sort.return_value.limit.return_value.to_pandas.return_value = (
        pd.DataFrame()
    )
    return sess


# ---------------------------------------------------------------------------
# run_ingestion -- success path
# ---------------------------------------------------------------------------

def test_run_ingestion_success_returns_summary(mock_session):
    run_id = str(uuid.uuid4())
    with patch("lib.ingest._synthetic_orders", return_value=MagicMock()):
        result = run_ingestion(mock_session, run_id, num_rows=42)

    assert result["run_id"] == run_id
    assert result["status"] == "SUCCESS"
    assert result["rows_loaded"] == 42


def test_run_ingestion_success_calls_save_as_table(mock_session):
    with patch("lib.ingest._synthetic_orders") as mock_builder:
        mock_df = MagicMock()
        mock_builder.return_value = mock_df
        run_ingestion(mock_session, str(uuid.uuid4()), num_rows=10)

    mock_df.write.mode.assert_called_once_with("append")
    mock_df.write.mode.return_value.save_as_table.assert_called_once()


def test_run_ingestion_success_logs_running_then_success(mock_session):
    run_id = str(uuid.uuid4())
    # Spy on lib.ingest.lit to capture the plain values passed to Column wrappers.
    with patch("lib.ingest._synthetic_orders", return_value=MagicMock()), \
         patch("lib.ingest.lit", wraps=real_lit) as mock_lit:
        run_ingestion(mock_session, run_id, num_rows=10)

    # _log_start: session.sql called with run_id and PROC_NAME as params
    first_sql_call = mock_session.sql.call_args_list[0]
    params = first_sql_call[1].get("params") or (
        first_sql_call[0][1] if len(first_sql_call[0]) > 1 else []
    )
    assert run_id in params
    assert PROC_NAME in params

    # _log_finish(SUCCESS): lit("SUCCESS") was called
    lit_values = [c.args[0] for c in mock_lit.call_args_list if c.args]
    assert "SUCCESS" in lit_values


# ---------------------------------------------------------------------------
# run_ingestion -- failure path
# ---------------------------------------------------------------------------

def test_run_ingestion_fail_reraises(mock_session):
    with pytest.raises(ValueError, match="Injected failure"):
        run_ingestion(mock_session, str(uuid.uuid4()), fail=True)


def test_run_ingestion_fail_logs_failed_status(mock_session):
    run_id = str(uuid.uuid4())
    with patch("lib.ingest.lit", wraps=real_lit) as mock_lit:
        with pytest.raises(ValueError):
            run_ingestion(mock_session, run_id, fail=True)

    lit_values = [c.args[0] for c in mock_lit.call_args_list if c.args]
    assert "FAILED" in lit_values


def test_run_ingestion_fail_error_message_captured(mock_session):
    run_id = str(uuid.uuid4())
    with patch("lib.ingest.lit", wraps=real_lit) as mock_lit:
        with pytest.raises(ValueError):
            run_ingestion(mock_session, run_id, fail=True)

    # lit(error_msg) is called with the error message string
    lit_str_values = [c.args[0] for c in mock_lit.call_args_list if c.args and isinstance(c.args[0], str)]
    assert any("Injected failure" in v for v in lit_str_values)


# ---------------------------------------------------------------------------
# get_kpis
# ---------------------------------------------------------------------------

def test_get_kpis_returns_all_keys(mock_session):
    row = MagicMock()
    row.__getitem__.side_effect = {
        "TOTAL_RUNS": 5,
        "FAILED_RUNS": 2,
        "SUCCESS_RUNS": 3,
        "ROWS_LOADED": 1500,
    }.__getitem__
    mock_session.sql.return_value.collect.return_value = [row]

    kpis = get_kpis(mock_session)
    assert set(kpis.keys()) == {"total_runs", "failed_runs", "success_runs", "rows_loaded"}


def test_get_kpis_values_match_row(mock_session):
    row = MagicMock()
    data = {"TOTAL_RUNS": 7, "FAILED_RUNS": 3, "SUCCESS_RUNS": 4, "ROWS_LOADED": 2000}
    row.__getitem__.side_effect = data.__getitem__
    mock_session.sql.return_value.collect.return_value = [row]

    kpis = get_kpis(mock_session)
    assert kpis["total_runs"] == 7
    assert kpis["failed_runs"] == 3
    assert kpis["success_runs"] == 4
    assert kpis["rows_loaded"] == 2000


# ---------------------------------------------------------------------------
# get_run_history
# ---------------------------------------------------------------------------

def test_get_run_history_returns_dataframe(mock_session):
    expected = pd.DataFrame({"STATUS": ["SUCCESS", "FAILED"], "RUN_ID": ["r1", "r2"]})
    mock_session.table.return_value.sort.return_value.limit.return_value.to_pandas.return_value = (
        expected
    )
    result = get_run_history(mock_session, limit=5)
    assert list(result.columns) == ["STATUS", "RUN_ID"]
    assert len(result) == 2


def test_get_run_history_passes_limit(mock_session):
    get_run_history(mock_session, limit=25)
    mock_session.table.return_value.sort.return_value.limit.assert_called_once_with(25)
