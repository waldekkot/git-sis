"""Tests for streamlit_app.py using Streamlit's AppTest framework.

AppTest simulates a running Streamlit app in-process — no browser, no server.
It exposes widget elements (button, toggle, number_input) for manipulation
and output elements (title, metric, success, error, warning) for assertion.

Ref: https://docs.streamlit.io/develop/api-reference/app-testing

The Snowflake session is mocked so tests run without credentials. Snowpark
logic is independently tested in test_ingest.py via the local testing framework.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

# Path to the Streamlit entry point, relative to the project root
# (where pytest is invoked and sys.path includes app/).
APP_FILE = "app/streamlit_app.py"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_session():
    """Build a MagicMock Snowpark session that satisfies get_kpis and get_run_history.

    get_kpis calls: table().count(), table().filter().count(),
                    table().filter().agg().collect()
    get_run_history calls: table().sort().limit().to_pandas()
    """
    sess = MagicMock(name="session")

    # Integer return values are required — kpis dict values are formatted
    # with f"{val:,}" which raises TypeError if val is a MagicMock.
    table_mock = MagicMock()
    table_mock.count.return_value = 5

    filter_mock = MagicMock()
    filter_mock.count.return_value = 2
    filter_mock.filter.return_value = filter_mock  # chaining support

    agg_row = MagicMock()
    agg_row.__getitem__ = lambda self, k: 1500
    agg_row.__bool__ = lambda self: True
    filter_mock.agg.return_value.collect.return_value = [agg_row]

    table_mock.filter.return_value = filter_mock
    table_mock.sort.return_value.limit.return_value.to_pandas.return_value = pd.DataFrame(
        {
            "RUN_ID": ["r1"],
            "STATUS": ["SUCCESS"],
            "ROWS_LOADED": [500],
            "PROC_NAME": ["LOAD_SYNTHETIC_ORDERS"],
            "STARTED_AT": [None],
            "ENDED_AT": [None],
            "ERROR_CODE": [None],
            "ERROR_MSG": [None],
        }
    )
    sess.table.return_value = table_mock
    return sess


@pytest.fixture()
def app():
    """Run the app once with a mocked session; return the AppTest instance."""
    with patch("lib.session.get_session", return_value=_mock_session()):
        return AppTest.from_file(APP_FILE).run()


# ---------------------------------------------------------------------------
# Basic rendering
# ---------------------------------------------------------------------------


def test_no_exception(app):
    """App renders without uncaught exceptions on a normal load."""
    assert not app.exception


def test_title(app):
    """App title is 'Ingestion Ops Console'."""
    assert app.title[0].value == "Ingestion Ops Console"


def test_four_kpi_metrics(app):
    """KPI section renders exactly 4 metric tiles."""
    assert len(app.metric) == 4


def test_run_button_present(app):
    """'Run ingestion' button is present."""
    assert app.button[0].label == "Run ingestion"


def test_toggle_defaults_to_false(app):
    """Force-a-failure toggle defaults to False."""
    assert app.toggle[0].label == "Force a failure"
    assert app.toggle[0].value is False


def test_number_input_defaults_to_500(app):
    """Rows-to-ingest input defaults to 500."""
    assert app.number_input[0].value == 500


# ---------------------------------------------------------------------------
# KPI failure path
# ---------------------------------------------------------------------------


def test_warning_when_session_fails():
    """When the Snowflake tables aren't accessible, st.warning and st.info are shown."""
    failing = MagicMock()
    failing.table.side_effect = RuntimeError("no table")
    with patch("lib.session.get_session", return_value=failing):
        at = AppTest.from_file(APP_FILE).run()
    assert not at.exception
    assert len(at.warning) == 1
    assert len(at.info) == 1


# ---------------------------------------------------------------------------
# Ingestion — success path
# ---------------------------------------------------------------------------


def test_button_click_calls_run_ingestion():
    """Clicking 'Run ingestion' calls run_ingestion with session + num_rows=500 + fail=False."""
    mock_result = {"run_id": "test-run-1", "rows_loaded": 500}
    with patch("lib.session.get_session", return_value=_mock_session()):
        at = AppTest.from_file(APP_FILE).run()
        with patch("lib.ingest.run_ingestion", return_value=mock_result) as mock_run:
            at.button[0].click().run()

    assert not at.exception
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs.get("num_rows") == 500
    assert mock_run.call_args.kwargs.get("fail") is False


def test_success_message_shown_after_ingestion():
    """After a successful run, st.success is rendered with rows_loaded in the message."""
    mock_result = {"run_id": "test-run-2", "rows_loaded": 250}
    with patch("lib.session.get_session", return_value=_mock_session()):
        at = AppTest.from_file(APP_FILE).run()
        with patch("lib.ingest.run_ingestion", return_value=mock_result):
            at.button[0].click().run()

    assert not at.exception
    assert len(at.success) == 1
    assert "250" in at.success[0].value


def test_custom_num_rows_passed_to_ingestion():
    """Setting num_rows to 100 passes that value to run_ingestion."""
    with patch("lib.session.get_session", return_value=_mock_session()):
        at = AppTest.from_file(APP_FILE).run()
        at.number_input[0].set_value(100)
        with patch(
            "lib.ingest.run_ingestion", return_value={"run_id": "r", "rows_loaded": 100}
        ) as mock_run:
            at.button[0].click().run()

    assert not at.exception
    # num_rows is passed as a keyword arg: run_ingestion(session, run_id, num_rows=100, ...)
    assert mock_run.call_args.kwargs.get("num_rows") == 100


# ---------------------------------------------------------------------------
# Ingestion — failure path
# ---------------------------------------------------------------------------


def test_error_shown_via_force_fail_toggle():
    """Enabling 'Force a failure' and clicking Run shows an error box.

    This exercises the real run_ingestion(fail=True) path end-to-end — the
    ValueError raised inside ingest.py is caught by streamlit_app.py and
    surfaced via st.error().
    """
    with patch("lib.session.get_session", return_value=_mock_session()):
        at = AppTest.from_file(APP_FILE).run()
        at.toggle[0].set_value(True).run()
        at.button[0].click().run()

    assert not at.exception
    assert len(at.error) == 1
    assert "FAILED" in at.error[0].value
    assert "Injected failure" in at.error[0].value


def test_error_shown_on_arbitrary_ingestion_exception():
    """Any exception from run_ingestion is caught by the app and shown via st.error."""
    with patch("lib.session.get_session", return_value=_mock_session()):
        at = AppTest.from_file(APP_FILE).run()
        with patch("lib.ingest.run_ingestion", side_effect=ValueError("db connection lost")):
            at.button[0].click().run()

    assert not at.exception
    assert len(at.error) == 1
    assert "db connection lost" in at.error[0].value
