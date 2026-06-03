-- =====================================================================
-- 00_setup_env.sql  -- idempotent environment + table setup
-- =====================================================================
-- Run locally (Phase 2/3) before the first `streamlit run`:
--   snow sql -c oregon-sedemo -f deploy/00_setup_env.sql
--
-- Uses CREATE OR ALTER for declarative, re-runnable, rollback-friendly DDL.
--
-- Multi-env (CICD) variant: replace the literal DB below with a Jinja var and
-- run via `snow git execute @APP_REPO/branches/main/deploy/* -D "environment='PROD_DB'"`
-- e.g.  USE DATABASE {{ environment }};   -- (Jinja resolved server-side)
-- For this single-target demo we use the concrete database.
-- =====================================================================

USE DATABASE SNOWFLAKE_LEARNING_DB;
CREATE SCHEMA IF NOT EXISTS GIT_SIS;
USE SCHEMA SNOWFLAKE_LEARNING_DB.GIT_SIS;

-- Raw landing table for synthetic orders.
CREATE OR ALTER TABLE SNOWFLAKE_LEARNING_DB.GIT_SIS.ORDERS (
    ORDER_ID     STRING,
    RUN_ID       STRING,
    CUSTOMER_ID  NUMBER,
    AMOUNT       FLOAT,
    REGION       STRING,
    ORDER_TS     TIMESTAMP_LTZ
);

-- Structured ingestion log (one row per run, RUNNING -> SUCCESS/FAILED).
CREATE OR ALTER TABLE SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_LOG (
    RUN_ID       STRING,
    PROC_NAME    STRING,
    STATUS       STRING,         -- RUNNING | SUCCESS | FAILED
    ROWS_LOADED  NUMBER,
    ERROR_CODE   STRING,
    ERROR_MSG    STRING,
    STARTED_AT   TIMESTAMP_LTZ,
    ENDED_AT     TIMESTAMP_LTZ
);

SELECT 'Setup complete' AS STATUS,
       CURRENT_DATABASE() AS DB,
       CURRENT_SCHEMA()   AS SCHEMA;
