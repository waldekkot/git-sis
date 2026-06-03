"""Unit tests for lib.config -- no Snowflake connection required."""

from __future__ import annotations

import importlib


def test_default_schema_fqn(monkeypatch):
    monkeypatch.delenv("GIT_SIS_SCHEMA", raising=False)
    import lib.config as cfg

    importlib.reload(cfg)
    assert cfg.SCHEMA_FQN == "SNOWFLAKE_LEARNING_DB.GIT_SIS"
    assert cfg.ORDERS_TABLE == "SNOWFLAKE_LEARNING_DB.GIT_SIS.ORDERS"
    assert cfg.INGEST_LOG_TABLE == "SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_LOG"


def test_env_override(monkeypatch):
    monkeypatch.setenv("GIT_SIS_SCHEMA", "MY_DB.MY_SCHEMA")
    import lib.config as cfg

    importlib.reload(cfg)
    assert cfg.SCHEMA_FQN == "MY_DB.MY_SCHEMA"
    assert cfg.ORDERS_TABLE == "MY_DB.MY_SCHEMA.ORDERS"
    assert cfg.INGEST_LOG_TABLE == "MY_DB.MY_SCHEMA.INGEST_LOG"


def test_table_names_derive_from_schema_fqn(monkeypatch):
    """Whatever SCHEMA_FQN is, ORDERS_TABLE and INGEST_LOG_TABLE are always suffixed correctly."""
    monkeypatch.setenv("GIT_SIS_SCHEMA", "X.Y")
    import lib.config as cfg

    importlib.reload(cfg)
    assert cfg.ORDERS_TABLE.startswith(cfg.SCHEMA_FQN)
    assert cfg.INGEST_LOG_TABLE.startswith(cfg.SCHEMA_FQN)
    assert cfg.ORDERS_TABLE.endswith(".ORDERS")
    assert cfg.INGEST_LOG_TABLE.endswith(".INGEST_LOG")
