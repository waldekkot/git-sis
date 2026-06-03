"""Unit tests for lib.session -- the local/SiS session seam.

Strategy:
- Patch `streamlit.cache_resource` to be the identity function so we can call
  get_session() without a running Streamlit app.
- Test the SiS branch (get_active_session succeeds) and the local branch
  (get_active_session raises, Session.builder used instead).
- Each test uses importlib.reload to get a fresh, unwrapped function.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch


def _passthrough_cache_resource(**_kwargs):
    """Drop-in replacement for st.cache_resource that just returns the function.
    Accepts keyword args like show_spinner= so the decorator call succeeds.
    """
    return lambda f: f


def _reload_session_module():
    """Reload lib.session so the patched cache_resource is picked up."""
    import lib.session as mod

    return importlib.reload(mod)


def test_get_session_returns_active_session_in_sis(monkeypatch):
    """SiS branch: get_active_session() succeeds -> its return value is returned."""
    mock_active = MagicMock(name="sis_session")
    monkeypatch.setattr("streamlit.cache_resource", _passthrough_cache_resource)

    with patch("snowflake.snowpark.context.get_active_session", return_value=mock_active):
        mod = _reload_session_module()
        result = mod.get_session()

    assert result is mock_active


def test_get_session_falls_back_to_builder_locally(monkeypatch):
    """Local branch: get_active_session() raises -> Session.builder.config().create()."""
    mock_local = MagicMock(name="local_session")
    monkeypatch.setattr("streamlit.cache_resource", _passthrough_cache_resource)

    with (
        patch(
            "snowflake.snowpark.context.get_active_session",
            side_effect=Exception("no active session"),
        ),
        patch("snowflake.snowpark.Session.builder") as mock_builder,
    ):
        mock_builder.config.return_value.create.return_value = mock_local
        mod = _reload_session_module()
        result = mod.get_session()

    assert result is mock_local


def test_get_session_uses_default_connection_name(monkeypatch):
    """Local branch: connection_name defaults to 'default' when env var is absent."""
    monkeypatch.setattr("streamlit.cache_resource", _passthrough_cache_resource)
    monkeypatch.delenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", raising=False)

    with (
        patch("snowflake.snowpark.context.get_active_session", side_effect=Exception),
        patch("snowflake.snowpark.Session.builder") as mock_builder,
    ):
        mock_builder.config.return_value.create.return_value = MagicMock()
        mod = _reload_session_module()
        mod.get_session()

    mock_builder.config.assert_called_with("connection_name", "default")


def test_get_session_reads_connection_name_from_env(monkeypatch):
    """Local branch: SNOWFLAKE_DEFAULT_CONNECTION_NAME overrides 'default'."""
    monkeypatch.setattr("streamlit.cache_resource", _passthrough_cache_resource)
    monkeypatch.setenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", "my-test-conn")

    with (
        patch("snowflake.snowpark.context.get_active_session", side_effect=Exception),
        patch("snowflake.snowpark.Session.builder") as mock_builder,
    ):
        mock_builder.config.return_value.create.return_value = MagicMock()
        mod = _reload_session_module()
        mod.get_session()

    mock_builder.config.assert_called_with("connection_name", "my-test-conn")
