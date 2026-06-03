"""Tests for streamlit_app.py combining Streamlit AppTest and Snowpark local testing.

Strategy
--------
* AppTest simulates the Streamlit UI in-process (no browser, no server).
  Ref: https://docs.streamlit.io/develop/api-reference/app-testing
* The Snowpark local testing emulator provides the session backend in-process.
  Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally
* Together they give end-to-end UI + data-layer tests with zero network:
  widget click -> real run_ingestion() -> real Snowpark DataFrame writes ->
  in-memory tables -> real get_kpis() reads -> correct UI values.

Mock inventory (three mocks only)
----------------------------------
1. `patch("lib.session.get_session", return_value=seeded_session)` — SESSION INJECTION,
   not a stub. A real Snowpark local testing session is provided; no Snowpark logic
   is bypassed.  This is the same pattern used to swap databases between environments.
2. `uuid_patch` fixture — patches `lib.ingest.call_function` for UUID_STRING.
   Pure emulator limitation (UUID_STRING not implemented), not business logic.
3. `MagicMock` in test_warning_when_session_fails — the one test that needs a
   controlled failure mode (tables inaccessible) to verify the UI error path.

Everything else — DataFrame operations, filter/count/agg/update, KPI calculations,
ingestion pipeline writes — runs against the real Snowpark emulator.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from snowflake.snowpark.functions import col, lit
from streamlit.testing.v1 import AppTest

from lib import config as _cfg

# Path to the Streamlit entry point, relative to the project root
# (where pytest is invoked and sys.path includes app/).
APP_FILE = "app/streamlit_app.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def snowpark_app(seeded_session, uuid_patch):  # noqa: ARG001 — uuid_patch is a context
    """AppTest backed by a real Snowpark local testing session.

    seeded_session (from conftest): empty ORDERS + INGEST_LOG tables, real emulator.
    uuid_patch (from conftest): UUID_STRING patched for the emulator; active for
    the entire fixture scope, covering all subsequent .run() calls in the test.

    Returns (AppTest, Session) so tests can inspect in-memory tables directly.
    """
    with patch("lib.session.get_session", return_value=seeded_session):
        at = AppTest.from_file(APP_FILE).run()
    return at, seeded_session


# ---------------------------------------------------------------------------
# Rendering — widget presence and defaults
# ---------------------------------------------------------------------------


def test_no_exception(snowpark_app):
    """App renders without uncaught exceptions on a normal load."""
    at, _ = snowpark_app
    assert not at.exception


def test_title(snowpark_app):
    """App title is 'Ingestion Ops Console'."""
    at, _ = snowpark_app
    assert at.title[0].value == "Ingestion Ops Console"


def test_run_button_present(snowpark_app):
    """'Run ingestion' button is present."""
    at, _ = snowpark_app
    assert at.button[0].label == "Run ingestion"


def test_toggle_defaults_to_false(snowpark_app):
    """Force-a-failure toggle defaults to False."""
    at, _ = snowpark_app
    assert at.toggle[0].label == "Force a failure"
    assert at.toggle[0].value is False


def test_number_input_defaults_to_500(snowpark_app):
    """Rows-to-ingest input defaults to 500."""
    at, _ = snowpark_app
    assert at.number_input[0].value == 500


# ---------------------------------------------------------------------------
# KPIs — real Snowpark emulator reads from in-memory tables
# ---------------------------------------------------------------------------


def test_initial_kpis_are_zero(snowpark_app):
    """On first load with no data, all KPI tiles show 0.

    This is a real Snowpark count() against the empty seeded tables —
    not a mocked return value.
    """
    at, _ = snowpark_app
    assert not at.exception
    assert len(at.metric) == 4
    assert at.metric[0].value == "0"  # Total runs
    assert at.metric[1].value == "0"  # Succeeded
    assert at.metric[2].value == "0"  # Failed
    assert at.metric[3].value == "0"  # Rows loaded


# ---------------------------------------------------------------------------
# KPI failure path — controlled error with MagicMock (justified)
# ---------------------------------------------------------------------------


def test_warning_when_session_fails():
    """When tables are inaccessible, st.warning + st.info are shown.

    This is the one test that uses a MagicMock session: we need a
    controlled failure mode (session.table raises) to exercise the
    UI error path.  All other tests use the real emulator.
    """
    failing = MagicMock()
    failing.table.side_effect = RuntimeError("no table")
    with patch("lib.session.get_session", return_value=failing):
        at = AppTest.from_file(APP_FILE).run()
    assert not at.exception
    assert len(at.warning) == 1
    assert len(at.info) == 1


# ---------------------------------------------------------------------------
# Ingestion success path — real Snowpark writes, data assertions
# ---------------------------------------------------------------------------


def test_button_click_writes_500_rows_to_orders(snowpark_app):
    """Button click runs real run_ingestion which writes 500 rows to ORDERS.

    This verifies the full pipeline: UI -> run_ingestion() -> _synthetic_orders()
    -> DataFrame.write.save_as_table() -> in-memory ORDERS table.
    No Snowpark logic is mocked.
    """
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.button[0].click().run()

    assert not at.exception
    assert len(at.success) == 1
    assert "500" in at.success[0].value

    # Real Snowpark count — the emulator actually wrote the rows
    assert sess.table(_cfg.ORDERS_TABLE).count() == 500
    assert sess.table(_cfg.INGEST_LOG_TABLE).filter(col("STATUS") == lit("SUCCESS")).count() == 1


def test_button_click_records_proc_name(snowpark_app):
    """INGEST_LOG entry is stamped with the expected PROC_NAME."""
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.button[0].click().run()

    log = sess.table(_cfg.INGEST_LOG_TABLE).collect()
    assert len(log) == 1
    assert log[0]["PROC_NAME"] == "LOAD_SYNTHETIC_ORDERS"


def test_custom_num_rows_writes_correct_count(snowpark_app):
    """Setting num_rows to 100 causes exactly 100 rows in ORDERS."""
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.number_input[0].set_value(100)
        at.button[0].click().run()

    assert sess.table(_cfg.ORDERS_TABLE).count() == 100


def test_orders_have_valid_regions(snowpark_app):
    """All ORDERS rows have a valid region (US/EU/APAC/LATAM)."""
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.number_input[0].set_value(40)
        at.button[0].click().run()

    rows = sess.table(_cfg.ORDERS_TABLE).collect()
    regions = {r["REGION"] for r in rows}
    assert regions <= {"US", "EU", "APAC", "LATAM"}
    assert len(regions) > 1, "Expected multiple regions across 40 rows"


def test_second_run_accumulates_rows(snowpark_app):
    """Two button clicks accumulate rows correctly (append mode)."""
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.button[0].click().run()
        at.button[0].click().run()

    assert sess.table(_cfg.ORDERS_TABLE).count() == 1000  # 2 × 500
    assert sess.table(_cfg.INGEST_LOG_TABLE).count() == 2


# ---------------------------------------------------------------------------
# Ingestion failure path — real run_ingestion(fail=True) via toggle
# ---------------------------------------------------------------------------


def test_force_fail_toggle_shows_error_and_logs_failure(snowpark_app):
    """Toggle Force a failure -> button click -> real ValueError -> st.error.

    This exercises run_ingestion(fail=True) end-to-end:
      - ingest.py raises ValueError (not mocked)
      - streamlit_app.py catches and shows st.error
      - INGEST_LOG is updated with STATUS=FAILED (real Snowpark write)
    """
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.toggle[0].set_value(True).run()
        at.button[0].click().run()

    assert not at.exception
    assert len(at.error) == 1
    assert "FAILED" in at.error[0].value
    assert "Injected failure" in at.error[0].value

    # Verify INGEST_LOG actually recorded the failure (real Snowpark assertion)
    assert sess.table(_cfg.INGEST_LOG_TABLE).filter(col("STATUS") == lit("FAILED")).count() == 1
    assert sess.table(_cfg.ORDERS_TABLE).count() == 0  # no rows written on failure


def test_error_shown_on_arbitrary_ingestion_exception(snowpark_app):
    """Any exception from run_ingestion is caught and shown via st.error.

    This tests the UI catch-all, not Snowpark logic — run_ingestion is
    patched to simulate an unexpected database error (e.g. network timeout).
    """
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        with patch("lib.ingest.run_ingestion", side_effect=ValueError("db connection lost")):
            at.button[0].click().run()

    assert not at.exception
    assert len(at.error) == 1
    assert "db connection lost" in at.error[0].value
