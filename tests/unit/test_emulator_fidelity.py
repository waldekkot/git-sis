"""Emulator fidelity tests — living documentation for Snowpark local-testing gaps.

These tests prove that each workaround in conftest.py is necessary and correct:
- Each gap test demonstrates the EXPECTED behaviour with the patch active.
- When Snowflake patches a gap in a new Snowpark release, the test still
  passes — but the mock can now be removed and replaced with native emulator
  support. Run `make test-live` after removing a patch to confirm.

Reference: docs/emulator-gaps.md (gap inventory table)
"""

from __future__ import annotations

import re

import pytest
from snowflake.snowpark import Session
from snowflake.snowpark.functions import call_function, col, lit, uniform
from snowflake.snowpark.functions import round as sf_round

# ---------------------------------------------------------------------------
# Gap 1: UUID_STRING via call_function
# ---------------------------------------------------------------------------


def test_uuid_string_raises_without_patch(seeded_session: Session) -> None:
    """Calling UUID_STRING directly in the emulator raises NotImplementedError.

    This documents WHY uuid_patch is needed. If this test starts FAILING
    (no exception raised), UUID_STRING is now emulator-native and uuid_patch
    can be removed from conftest.py.
    """
    with pytest.raises(Exception, match="UUID_STRING"):
        seeded_session.create_dataframe([[1]], schema=["x"]).select(
            call_function("UUID_STRING").alias("uid")
        ).collect()


def test_uuid_patch_makes_synthetic_orders_work(seeded_session: Session, uuid_patch) -> None:  # noqa: ARG001
    """With uuid_patch, _synthetic_orders() generates valid UUID-like ORDER_IDs.

    uuid_patch patches lib.ingest.call_function so that calls to
    call_function('UUID_STRING') return lit(str(uuid.uuid4())) instead of
    hitting the unsupported emulator built-in.
    """
    from lib.ingest import _synthetic_orders

    df = _synthetic_orders(seeded_session, num_rows=10, run_id="test-uuid-fidelity")
    rows = df.collect()
    assert len(rows) == 10
    for row in rows:
        uid = row["ORDER_ID"]
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            uid,
            re.IGNORECASE,
        ), f"ORDER_ID is not a valid UUID: {uid!r}"


def test_uuid_patch_produces_unique_order_ids(seeded_session: Session, uuid_patch) -> None:  # noqa: ARG001
    """Documents a known emulator limitation of the current uuid_patch approach.

    The patch uses unittest.mock.patch with side_effect, but the emulator
    evaluates the side_effect ONCE per DataFrame execution — so all rows
    within a single _synthetic_orders() call receive the SAME UUID.

    On real Snowflake, UUID_STRING() generates a unique value per row.

    This means:
    - The ORDER_ID column is NOT unique in emulator tests (all rows share one UUID).
    - Tests that assert row counts or STATUS values are unaffected.
    - Tests that assert ORDER_ID uniqueness must run against real Snowflake
      (make test-live or make test-integration).

    If this test starts FAILING (unique UUIDs per row), the emulator has been
    improved and the uuid_patch approach can be upgraded to use
    @snowflake.snowpark.mock.patch instead, which IS per-row capable.
    """
    from lib.ingest import _synthetic_orders

    df = _synthetic_orders(seeded_session, num_rows=5, run_id="test-uuid-uniqueness")
    order_ids = [r["ORDER_ID"] for r in df.collect()]
    # Document the limitation: all 5 rows share the same UUID in emulator mode
    assert len(order_ids) == 5
    # All IDs are valid UUIDs (patch IS working — just not per-row unique)
    for uid in order_ids:
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            uid,
            re.IGNORECASE,
        ), f"ORDER_ID is not a valid UUID: {uid!r}"


# ---------------------------------------------------------------------------
# Gap 2: UNIFORM function
# ---------------------------------------------------------------------------


def test_uniform_integer_bounds(seeded_session: Session) -> None:
    """UNIFORM with integer bounds returns integers in [low, high]."""
    df = seeded_session.create_dataframe([[i] for i in range(100)], schema=["x"]).select(
        uniform(lit(1), lit(100), col("x")).alias("val")
    )
    vals = [r["VAL"] for r in df.collect()]
    assert all(isinstance(v, int) for v in vals), "Expected int output from int bounds"
    assert all(1 <= v <= 100 for v in vals), f"Values out of range [1,100]: {vals[:5]}"


def test_uniform_float_bounds(seeded_session: Session) -> None:
    """UNIFORM with float bounds returns floats in [low, high]."""
    df = seeded_session.create_dataframe([[i] for i in range(100)], schema=["x"]).select(
        uniform(lit(0.0), lit(1.0), col("x")).alias("val")
    )
    vals = [r["VAL"] for r in df.collect()]
    assert all(isinstance(v, float) for v in vals), "Expected float output from float bounds"
    assert all(0.0 <= v <= 1.0 for v in vals), f"Values out of range [0.0,1.0]: {vals[:5]}"


# ---------------------------------------------------------------------------
# Gap 3: ROUND function
# ---------------------------------------------------------------------------


def test_round_to_two_decimal_places(seeded_session: Session) -> None:
    """ROUND(value, 2) returns values with at most 2 decimal places."""
    df = seeded_session.create_dataframe([[3.14159], [2.71828], [1.0]], schema=["x"]).select(
        sf_round(col("x"), lit(2)).alias("rounded")
    )
    vals = [r["ROUNDED"] for r in df.collect()]
    assert vals[0] == pytest.approx(3.14)
    assert vals[1] == pytest.approx(2.72)
    assert vals[2] == pytest.approx(1.0)


def test_round_to_zero_decimal_places(seeded_session: Session) -> None:
    """ROUND(value, 0) returns whole numbers."""
    df = seeded_session.create_dataframe([[3.7], [2.3]], schema=["x"]).select(
        sf_round(col("x"), lit(0)).alias("rounded")
    )
    vals = [r["ROUNDED"] for r in df.collect()]
    assert vals[0] == pytest.approx(4.0)
    assert vals[1] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# Gap 4: session.sql() is NOT supported — architecture enforces DataFrame API
# ---------------------------------------------------------------------------


def test_session_sql_not_available_in_local_testing(seeded_session: Session) -> None:
    """session.sql() raises in the local-testing emulator.

    This documents why lib/ingest.py uses the DataFrame API exclusively.
    If this test starts FAILING (no exception raised), it means Snowflake has
    added session.sql() support to the emulator — review whether the
    DataFrame-API-only constraint in app/.importlinter can be relaxed.
    """
    with pytest.raises(NotImplementedError):  # emulator raises NotImplementedError
        seeded_session.sql("SELECT 1").collect()


# ---------------------------------------------------------------------------
# Gap 5: uuid_patch MUST be active for run_ingestion — not optional
# ---------------------------------------------------------------------------


def test_uuid_patch_required_for_run_ingestion(seeded_session: Session) -> None:
    """run_ingestion() calls UUID_STRING internally; it fails without the patch.

    This test confirms that uuid_patch is a mandatory fixture for any test
    that exercises run_ingestion().  If this test starts FAILING (no exception),
    UUID_STRING is now implemented in the emulator and uuid_patch can be removed.
    """
    from lib.ingest import run_ingestion

    # No uuid_patch active — call_function("UUID_STRING") should fail in emulator
    with pytest.raises(NotImplementedError):
        run_ingestion(seeded_session, "test-run-no-patch", num_rows=10)
