"""Shared fixtures and local-testing patches for unit tests.

Snowflake local testing framework reference:
  https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally

Module-level @patch decorators register mock implementations for Snowflake
built-in functions that are not yet implemented in the local testing emulator
(uniform, round).  These patches are active for every local_testing session
created in this process.
"""

from __future__ import annotations

import random as py_random

import pytest
from snowflake.snowpark import Session
from snowflake.snowpark.functions import round as sf_round
from snowflake.snowpark.functions import uniform as sf_uniform
from snowflake.snowpark.mock import ColumnEmulator, ColumnType, patch
from snowflake.snowpark.types import DoubleType, LongType

# ---------------------------------------------------------------------------
# Patches for functions not implemented in the local testing emulator
# ---------------------------------------------------------------------------


@patch(sf_uniform)
def _mock_uniform(start, end, gen) -> ColumnEmulator:
    """UNIFORM(low, high, gen) → random values in [low, high].

    From the Snowflake mock docs: LiteralType args are passed as plain Python
    values; ColumnOrName args arrive as ColumnEmulator objects.
    `lit(1)` and `lit(1000)` are literals; `random()` is a ColumnOrName.
    Integer bounds produce integer output; float bounds produce float output.
    """
    n = len(gen) if hasattr(gen, "__len__") else 1
    s = start.iloc[0] if hasattr(start, "iloc") else start
    e = end.iloc[0] if hasattr(end, "iloc") else end
    if isinstance(s, int) and isinstance(e, int):
        data = [py_random.randint(int(s), int(e)) for _ in range(n)]
        sf_type = ColumnType(LongType(), False)
    else:
        data = [py_random.uniform(float(s), float(e)) for _ in range(n)]
        sf_type = ColumnType(DoubleType(), False)
    result = ColumnEmulator(data=data)
    result.sf_type = sf_type
    return result


@patch(sf_round)
def _mock_round(value, scale=0) -> ColumnEmulator:
    """ROUND(value, scale) → value rounded to `scale` decimal places."""
    scale_int = int(scale.iloc[0]) if hasattr(scale, "iloc") else int(scale)
    data = [round(float(v), scale_int) if v is not None else None for v in value]
    result = ColumnEmulator(data=data)
    result.sf_type = ColumnType(DoubleType(), False)
    return result


# ---------------------------------------------------------------------------
# Session fixture
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --snowflake-session option per Snowflake testing docs convention."""
    parser.addoption(
        "--snowflake-session",
        action="store",
        default="local",
        help="'local' (default) uses the in-process emulator; 'live' connects to Snowflake.",
    )


@pytest.fixture(scope="module")
def local_session(request) -> Session:
    """Module-scoped local-testing session — no credentials, no network.

    Compatible with --snowflake-session option: pass --snowflake-session=live
    (with SNOWFLAKE_DEFAULT_CONNECTION_NAME set) to run unit tests against real
    Snowflake instead of the emulator.
    """
    mode = request.config.getoption("--snowflake-session", default="local")
    if mode == "local":
        sess = Session.builder.config("local_testing", True).create()
    else:
        import os

        conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME", "default")
        sess = Session.builder.config("connection_name", conn).create()
    yield sess
    sess.close()
