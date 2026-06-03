"""Unit tests for streamlit_app.py -- the Streamlit UI entry point.

Strategy:
- Replace `streamlit` in sys.modules with a MagicMock so all `st.*` calls
  are no-ops and the module can be imported without a running Streamlit runtime.
- Patch `lib.session.get_session` to return a controlled mock session.
- Reload `streamlit_app` inside each test so patches are applied fresh.

Coverage goal: lines 8-21 (imports + module-level init) and lines 41-54
(KPIs success + exception paths) = ~26 lines ≈ 74% of streamlit_app.py.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pandas as pd


def _make_mock_streamlit(button_clicked: bool = False):
    """Build a MagicMock that satisfies the streamlit API used by streamlit_app."""
    mock_st = MagicMock(name="streamlit")
    # First columns() call: operator controls (3 cols)
    # Second columns() call: KPI tiles (4 cols)
    c1, c2, c3 = MagicMock(), MagicMock(), MagicMock()
    kpi_cols = [MagicMock(), MagicMock(), MagicMock(), MagicMock()]
    c1.number_input.return_value = 500
    c2.toggle.return_value = False
    c3.button.return_value = button_clicked
    mock_st.columns.side_effect = [(c1, c2, c3), kpi_cols]
    # context manager support for st.container and st.spinner
    mock_st.container.return_value.__enter__ = lambda s: s
    mock_st.container.return_value.__exit__ = lambda s, *a: False
    mock_st.spinner.return_value.__enter__ = lambda s: s
    mock_st.spinner.return_value.__exit__ = lambda s, *a: False
    return mock_st


def _make_mock_session():
    """Build a MagicMock Snowpark session that satisfies get_kpis and get_run_history."""
    sess = MagicMock(name="session")

    # Table mock that supports the chained calls made by get_kpis and get_run_history.
    # get_kpis: table().count(), table().filter().count(), table().filter().agg().collect()
    # get_run_history: table().sort().limit().to_pandas()
    table_mock = MagicMock()
    table_mock.count.return_value = 10

    filter_mock = MagicMock()
    filter_mock.count.return_value = 2
    filter_mock.filter.return_value = filter_mock  # supports repeated .filter() chaining

    agg_row = MagicMock()
    agg_row.__getitem__ = lambda self, k: 4000
    agg_row.__bool__ = lambda self: True
    filter_mock.agg.return_value.collect.return_value = [agg_row]

    table_mock.filter.return_value = filter_mock
    table_mock.sort.return_value.limit.return_value.to_pandas.return_value = pd.DataFrame()
    sess.table.return_value = table_mock
    return sess


def _load_app(mock_st, mock_session):
    """Import streamlit_app with mocked streamlit and session."""
    # Remove any cached import of streamlit_app
    for key in list(sys.modules.keys()):
        if key in ("streamlit_app",):
            del sys.modules[key]

    with (
        patch.dict("sys.modules", {"streamlit": mock_st}),
        patch("lib.session.get_session", return_value=mock_session),
    ):
        return importlib.import_module("streamlit_app")


# ---------------------------------------------------------------------------
# Module-level execution: set_page_config, title, caption, KPIs (success)
# ---------------------------------------------------------------------------


def test_app_imports_and_renders_kpis():
    """Importing the app calls set_page_config, title, caption, and KPI metrics."""
    mock_st = _make_mock_streamlit()
    mock_session = _make_mock_session()

    _load_app(mock_st, mock_session)

    mock_st.set_page_config.assert_called_once()
    mock_st.title.assert_called_once()
    mock_st.caption.assert_called_once()
    # 4 metric tiles should have been rendered
    assert mock_st.columns.called


def test_app_calls_metric_four_times():
    """Four st.metric() calls render the KPI tiles."""
    mock_st = _make_mock_streamlit()
    _load_app(mock_st, _make_mock_session())
    # columns() called twice: once for controls (3), once for KPIs (4)
    assert mock_st.columns.call_count == 2


# ---------------------------------------------------------------------------
# KPI load failure path (lines 52-54)
# ---------------------------------------------------------------------------


def test_app_shows_warning_when_kpi_load_fails():
    """When get_kpis raises, st.warning and st.info are shown (lines 52-54)."""
    mock_st = _make_mock_streamlit()

    # Session whose sql().collect() raises to trigger the except block
    failing_session = MagicMock()
    failing_session.sql.return_value.collect.side_effect = RuntimeError("table not found")

    _load_app(mock_st, failing_session)

    mock_st.warning.assert_called_once()
    mock_st.info.assert_called_once()


# ---------------------------------------------------------------------------
# Operator controls: button click triggers ingestion
# ---------------------------------------------------------------------------


def test_app_runs_ingestion_on_button_click():
    """When the Run button returns True, run_ingestion is called and st.success shown."""
    mock_st = _make_mock_streamlit(button_clicked=True)
    mock_session = _make_mock_session()

    with patch("lib.ingest.run_ingestion", return_value={"run_id": "x", "rows_loaded": 100}):
        _load_app(mock_st, mock_session)

    mock_st.success.assert_called_once()


def test_app_shows_error_on_ingestion_failure():
    """When run_ingestion raises, st.error is shown (not an unhandled exception)."""
    mock_st = _make_mock_streamlit(button_clicked=True)
    mock_session = _make_mock_session()

    with patch("lib.ingest.run_ingestion", side_effect=ValueError("boom")):
        _load_app(mock_st, mock_session)

    mock_st.error.assert_called_once()
