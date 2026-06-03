"""Snowpark synthetic data ingestion with structured logging and error handling.

Pattern (mirrors a production ingestion stored procedure):
  1. Write a RUNNING row to INGEST_LOG.
  2. Do the work (generate synthetic orders, append to ORDERS).
  3. On success -> UPDATE the row to SUCCESS with rows_loaded.
     On failure -> UPDATE the row to FAILED with the captured error, then
     re-raise so the caller surfaces it (errors are recorded, never swallowed).

The same function runs unchanged locally and inside SiS because it only touches
the Snowpark `session` it is handed.
"""

from __future__ import annotations

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

from lib import config as _cfg  # module reference so test reloads propagate

PROC_NAME = "LOAD_SYNTHETIC_ORDERS"


def _log_start(session: Session, run_id: str) -> None:
    """Insert a RUNNING row. Parameterized -- never interpolate run_id into SQL."""
    session.sql(
        f"INSERT INTO {_cfg.INGEST_LOG_TABLE} "
        "(RUN_ID, PROC_NAME, STATUS, STARTED_AT) "
        "SELECT ?, ?, 'RUNNING', CURRENT_TIMESTAMP()",
        params=[run_id, PROC_NAME],
    ).collect()


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
    """Return headline KPIs computed in Snowflake."""
    row = session.sql(
        f"""
        SELECT
            COUNT(*)                                          AS TOTAL_RUNS,
            COUNT_IF(STATUS = 'FAILED')                       AS FAILED_RUNS,
            COUNT_IF(STATUS = 'SUCCESS')                      AS SUCCESS_RUNS,
            COALESCE(SUM(IFF(STATUS = 'SUCCESS', ROWS_LOADED, 0)), 0) AS ROWS_LOADED
        FROM {_cfg.INGEST_LOG_TABLE}
        """
    ).collect()[0]
    return {
        "total_runs": row["TOTAL_RUNS"],
        "failed_runs": row["FAILED_RUNS"],
        "success_runs": row["SUCCESS_RUNS"],
        "rows_loaded": row["ROWS_LOADED"],
    }
