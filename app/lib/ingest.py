"""Snowpark synthetic data ingestion with structured logging and error handling.

Pattern (mirrors a production ingestion stored procedure):
  1. Write a RUNNING row to INGEST_LOG.
  2. Do the work (generate synthetic orders, append to ORDERS).
  3. On success -> UPDATE the row to SUCCESS with rows_loaded.
     On failure -> UPDATE the row to FAILED with the captured error, then
     re-raise so the caller surfaces it (errors are recorded, never swallowed).

The same function runs unchanged locally and inside SiS because it only touches
the Snowpark `session` it is handed.

Local-testing compatibility (https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally):
  session.sql() is not supported in local testing.  All operations here use
  the DataFrame API so unit tests can run fully in-process with
  Session.builder.config("local_testing", True).create().
"""

from __future__ import annotations

import datetime
import uuid as _uuid

from snowflake.snowpark import Session
from snowflake.snowpark.functions import (
    call_function,
    col,
    current_timestamp,
    lit,
    random,
    uniform,
    when,
)
from snowflake.snowpark.functions import (
    round as sf_round,
)
from snowflake.snowpark.functions import (
    sum as sf_sum,
)
from snowflake.snowpark.types import (
    LongType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from lib import config as _cfg  # module reference so test reloads propagate

PROC_NAME = "LOAD_SYNTHETIC_ORDERS"
PURGE_PROC_NAME = "PURGE_ORDERS"

# Schema for INGEST_LOG -- used when appending new log rows via DataFrame API.
_LOG_SCHEMA = StructType(
    [
        StructField("RUN_ID", StringType()),
        StructField("PROC_NAME", StringType()),
        StructField("STATUS", StringType()),
        StructField("ROWS_LOADED", LongType()),
        StructField("ERROR_CODE", StringType()),
        StructField("ERROR_MSG", StringType()),
        StructField("STARTED_AT", TimestampType()),
        StructField("ENDED_AT", TimestampType()),
    ]
)


def _log_start(session: Session, run_id: str) -> None:
    """Insert a RUNNING row via DataFrame API.

    session.sql(INSERT ...) is not supported in the local testing emulator,
    so we use create_dataframe().write.save_as_table() instead.
    """
    session.create_dataframe(
        [
            [
                run_id,
                PROC_NAME,
                "RUNNING",
                None,
                None,
                None,
                datetime.datetime.now(datetime.UTC),
                None,
            ]
        ],
        schema=_LOG_SCHEMA,
    ).write.mode("append").save_as_table(_cfg.INGEST_LOG_TABLE)


def _log_finish(
    session: Session,
    run_id: str,
    status: str,
    rows_loaded: int | None = None,
    error_msg: str | None = None,
) -> None:
    """Update the run's log row to a terminal state."""
    updates = {
        "STATUS": lit(status),
        "ENDED_AT": current_timestamp(),
        "ROWS_LOADED": lit(rows_loaded),
        "ERROR_MSG": lit(error_msg[:1000] if error_msg else None),
    }
    session.table(_cfg.INGEST_LOG_TABLE).update(updates, col("RUN_ID") == lit(run_id))


def _synthetic_orders(session: Session, run_id: str, num_rows: int):
    """Build a synthetic ORDERS DataFrame entirely server-side."""
    bucket = col("ID") % lit(4)
    region = (
        when(bucket == lit(0), lit("US"))
        .when(bucket == lit(1), lit("EU"))
        .when(bucket == lit(2), lit("APAC"))
        .otherwise(lit("LATAM"))
    )
    return session.range(num_rows).select(
        call_function("UUID_STRING").alias("ORDER_ID"),
        lit(run_id).alias("RUN_ID"),
        uniform(lit(1), lit(1000), random()).alias("CUSTOMER_ID"),
        sf_round(uniform(lit(10.0), lit(500.0), random()), 2).alias("AMOUNT"),
        region.alias("REGION"),
        current_timestamp().alias("ORDER_TS"),
    )


def run_ingestion(
    session: Session,
    run_id: str,
    num_rows: int = 500,
    fail: bool = False,
) -> dict:
    """Run one synthetic ingestion, logging RUNNING -> SUCCESS/FAILED.

    Args:
        session: Snowpark session (local-built or SiS active session).
        run_id: Unique id for this run (also stamped on every ORDERS row).
        num_rows: How many synthetic orders to generate.
        fail: If True, inject a failure to exercise the error path.

    Returns:
        A summary dict on success.

    Raises:
        Re-raises any exception after recording it to INGEST_LOG.
    """
    _log_start(session, run_id)
    try:
        if fail:
            raise ValueError("Injected failure (demo of the error path)")

        df = _synthetic_orders(session, run_id, num_rows)
        df.write.mode("append").save_as_table(_cfg.ORDERS_TABLE)

        _log_finish(session, run_id, "SUCCESS", rows_loaded=num_rows)
        return {"run_id": run_id, "status": "SUCCESS", "rows_loaded": num_rows}
    except Exception as exc:  # noqa: BLE001 - record then re-raise
        _log_finish(session, run_id, "FAILED", error_msg=str(exc))
        raise


# --- Read helpers for the UI -------------------------------------------------


def get_run_history(session: Session, limit: int = 100):
    """Return recent runs as a pandas DataFrame for display."""
    return (
        session.table(_cfg.INGEST_LOG_TABLE).sort(col("STARTED_AT").desc()).limit(limit).to_pandas()
    )


def get_kpis(session: Session) -> dict:
    """Return headline KPIs using the DataFrame API (compatible with local testing).

    Uses separate filter().count() calls rather than a single SQL aggregate so
    that Session.sql() (unsupported in local testing) is not needed.
    """
    df = session.table(_cfg.INGEST_LOG_TABLE)
    total = df.count()
    failed = df.filter(col("STATUS") == lit("FAILED")).count()
    success = df.filter(col("STATUS") == lit("SUCCESS")).count()
    rows_data = (
        df.filter(col("STATUS") == lit("SUCCESS"))
        .agg(sf_sum(col("ROWS_LOADED")).alias("TOTAL"))
        .collect()
    )
    rows_loaded = int(rows_data[0]["TOTAL"] or 0) if rows_data and rows_data[0]["TOTAL"] else 0
    return {
        "total_runs": total,
        "failed_runs": failed,
        "success_runs": success,
        "rows_loaded": rows_loaded,
    }


def purge_orders(session: Session) -> int:
    """Delete all rows from ORDERS and log a PURGE_ORDERS event to INGEST_LOG.

    Uses DataFrame.delete() — the Snowpark API for row deletion. This is
    compatible with the local testing emulator (no session.sql() used).

    Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/working-with-dataframes

    Args:
        session: Snowpark session (local-built or SiS active session).

    Returns:
        Number of rows deleted from ORDERS.
    """
    # Count first so we can report it even after deletion.
    # count() is a Snowpark action that works in the local testing emulator.
    rows_to_delete = session.table(_cfg.ORDERS_TABLE).count()

    # Delete all rows using the DataFrame API.
    # DataFrame.delete() translates to DELETE FROM <table> with no WHERE clause.
    session.table(_cfg.ORDERS_TABLE).delete()

    # Record the purge event in INGEST_LOG for auditability.
    run_id = str(_uuid.uuid4())
    now = datetime.datetime.now(datetime.UTC)
    session.create_dataframe(
        [[run_id, PURGE_PROC_NAME, "SUCCESS", rows_to_delete, None, None, now, now]],
        schema=_LOG_SCHEMA,
    ).write.mode("append").save_as_table(_cfg.INGEST_LOG_TABLE)

    return rows_to_delete
