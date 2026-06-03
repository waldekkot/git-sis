"""Central configuration for table locations.

In SiS the env var is unset, so the constants below resolve to the deploy
target. Locally you can override the schema with GIT_SIS_SCHEMA if you test
against a different schema. Fully-qualified names are used everywhere so the
code never depends on session context (Snowpark best practice).
"""

from __future__ import annotations

import os

# DB.SCHEMA that holds ORDERS + INGEST_LOG. Same value locally and in SiS.
SCHEMA_FQN = os.getenv("GIT_SIS_SCHEMA", "SNOWFLAKE_LEARNING_DB.GIT_SIS")

ORDERS_TABLE = f"{SCHEMA_FQN}.ORDERS"
INGEST_LOG_TABLE = f"{SCHEMA_FQN}.INGEST_LOG"
