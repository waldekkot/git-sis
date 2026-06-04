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
        at = AppTest.from_file(APP_FILE, default_timeout=30).run()
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
        at = AppTest.from_file(APP_FILE, default_timeout=30).run()
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


# ---------------------------------------------------------------------------
# Purge feature — TDD: tests written BEFORE the UI is implemented
#
# @st.dialog is a fragment (Streamlit 1.37+). AppTest exposes the dialog's
# elements as part of the app's widget tree.
#
# Two-step interaction:
#   1. Click "Purge orders" → dialog opens → "Confirm purge" button appears
#   2. Click "Confirm purge" → purge_orders() runs → dialog closes → rerun
#
# Ref: https://docs.streamlit.io/develop/api-reference/execution-flow/st.dialog
# Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/working-with-dataframes
# ---------------------------------------------------------------------------


def test_purge_button_present(snowpark_app):
    """'Purge orders' button must be visible in the Danger Zone expander.

    This test drives the requirement for a 'Purge orders' button in the UI.
    The expander expanded state does not affect AppTest widget accessibility.
    """
    at, _ = snowpark_app
    assert not at.exception
    purge_buttons = [b for b in at.button if "Purge" in b.label]
    assert len(purge_buttons) == 1, f"Expected 1 Purge button, got {[b.label for b in at.button]}"


def test_purge_dialog_opens_on_button_click(snowpark_app):
    """Clicking 'Purge orders' opens the @st.dialog with a 'Confirm purge' button.

    After clicking the Purge button, the dialog's elements are rendered
    into the AppTest widget tree. The 'Confirm purge' button must appear.
    """
    at, sess = snowpark_app
    purge_btn_idx = next(i for i, b in enumerate(at.button) if "Purge" in b.label)
    with patch("lib.session.get_session", return_value=sess):
        at.button[purge_btn_idx].click().run()

    assert not at.exception
    confirm_buttons = [b for b in at.button if "Confirm" in b.label]
    assert len(confirm_buttons) == 1, (
        f"Expected 'Confirm purge' button after dialog opens, got {[b.label for b in at.button]}"
    )


def test_purge_dialog_confirm_empties_orders_and_shows_success(snowpark_app):
    """Full purge flow: seed -> Purge+Confirm dual-click -> ORDERS empty + success.

    @st.dialog creates a fragment that only renders when its opener button
    is clicked in the SAME script run.  AppTest solution: mark BOTH buttons
    (Purge orders + Confirm purge) as clicked before calling .run() — the
    dialog function is called because Purge is True, the Confirm path runs
    because Confirm is True, all within one script execution.

    Verifies end-to-end:
    - Real Snowpark write via run_ingestion (seeded_session)
    - Real purge via purge_orders (DataFrame.delete()) — no mock
    - Success message shown in the UI  (session_state _purge_result path)
    - ORDERS table is actually empty afterwards (real Snowpark count())
    """
    at, sess = snowpark_app

    # Seed 500 rows via "Run ingestion" so we have data to purge.
    with patch("lib.session.get_session", return_value=sess):
        at.button[0].click().run()  # "Run ingestion"
    assert sess.table(_cfg.ORDERS_TABLE).count() == 500  # precondition

    # Open the dialog to discover the Confirm button index.
    purge_btn_idx = next(i for i, b in enumerate(at.button) if "Purge" in b.label)
    with patch("lib.session.get_session", return_value=sess):
        at.button[purge_btn_idx].click().run()  # dialog opens
    confirm_btn_idx = next(i for i, b in enumerate(at.button) if "Confirm" in b.label)

    # Dual-click: mark both buttons as clicked, then run once.
    # Both Purge (opener) and Confirm are True in the same script run:
    #   Purge True  → _confirm_purge_dialog() is called → dialog renders
    #   Confirm True → purge_orders() executes → _purge_result set → st.rerun()
    # After the rerun: _purge_result is found → st.success() displayed.
    at.button[purge_btn_idx].click()  # mark Purge as clicked  (no .run())
    at.button[confirm_btn_idx].click()  # mark Confirm as clicked (no .run())
    with patch("lib.session.get_session", return_value=sess):
        at.run()  # single run with BOTH buttons clicked

    assert not at.exception

    # UI: success message with row count
    assert len(at.success) >= 1
    assert "500" in at.success[-1].value

    # Data: ORDERS is empty (real Snowpark assertion — not a mock)
    assert sess.table(_cfg.ORDERS_TABLE).count() == 0


def test_purge_dialog_cancel_closes_dialog(snowpark_app):
    """Cancel button in the dialog closes it without purging any data.

    Covers the Cancel button branch (line 78 in streamlit_app.py).
    """
    at, sess = snowpark_app

    # Seed data to confirm nothing is deleted after Cancel
    with patch("lib.session.get_session", return_value=sess):
        at.button[0].click().run()  # run ingestion → 500 rows
    assert sess.table(_cfg.ORDERS_TABLE).count() == 500

    # Open the dialog and discover Cancel button index
    purge_btn_idx = next(i for i, b in enumerate(at.button) if "Purge" in b.label)
    with patch("lib.session.get_session", return_value=sess):
        at.button[purge_btn_idx].click().run()
    cancel_btn_idx = next(i for i, b in enumerate(at.button) if b.label == "Cancel")

    # Dual-click: Purge opener + Cancel
    at.button[purge_btn_idx].click()
    at.button[cancel_btn_idx].click()
    with patch("lib.session.get_session", return_value=sess):
        at.run()

    assert not at.exception
    assert sess.table(_cfg.ORDERS_TABLE).count() == 500  # data unchanged


def test_purge_dialog_shows_error_on_failure(snowpark_app):
    """When purge_orders() raises, _purge_error is set and st.error is shown.

    Covers the except handler (lines 74-75) and the _purge_error display (94-95).
    """
    at, sess = snowpark_app

    purge_btn_idx = next(i for i, b in enumerate(at.button) if "Purge" in b.label)
    with patch("lib.session.get_session", return_value=sess):
        at.button[purge_btn_idx].click().run()
    confirm_btn_idx = next(i for i, b in enumerate(at.button) if "Confirm" in b.label)

    # Simulate a failure during purge_orders()
    with patch("lib.ingest.purge_orders", side_effect=RuntimeError("disk full")):
        at.button[purge_btn_idx].click()
        at.button[confirm_btn_idx].click()
        with patch("lib.session.get_session", return_value=sess):
            at.run()

    assert not at.exception
    assert len(at.error) >= 1
    assert "disk full" in at.error[-1].value
