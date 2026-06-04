-- deploy/seed_data.sql — sample data for local development
--
-- Inserts a realistic set of rows into GIT_SIS.ORDERS and GIT_SIS.INGEST_LOG
-- so the app has data to display immediately after `make setup`.
--
-- Usage:
--   make seed                         # seeds the default schema (GIT_SIS)
--   make seed GIT_SIS_SCHEMA=MY_DEV   # seeds a personal sandbox schema
--
-- Note: uses INSERT OR OVERWRITE logic via TRUNCATE + INSERT so re-running
-- is safe (idempotent). Does NOT affect test isolation schemas
-- (GIT_SIS_TEST_*) which are managed by the integration test fixtures.

USE DATABASE SNOWFLAKE_LEARNING_DB;
USE SCHEMA GIT_SIS;

-- Seed INGEST_LOG with a mix of outcomes
INSERT INTO INGEST_LOG (RUN_ID, PROC_NAME, STATUS, ROWS_LOADED, ERROR_CODE, ERROR_MSG, STARTED_AT, ENDED_AT)
SELECT * FROM VALUES
    ('seed-run-001', 'ingest_orders', 'SUCCESS', 500,  NULL,   NULL,                         DATEADD('minute', -60, CURRENT_TIMESTAMP), DATEADD('minute', -59, CURRENT_TIMESTAMP)),
    ('seed-run-002', 'ingest_orders', 'SUCCESS', 250,  NULL,   NULL,                         DATEADD('minute', -45, CURRENT_TIMESTAMP), DATEADD('minute', -44, CURRENT_TIMESTAMP)),
    ('seed-run-003', 'ingest_orders', 'FAILED',    0,  'E001', 'Simulated failure (seeded)', DATEADD('minute', -30, CURRENT_TIMESTAMP), DATEADD('minute', -30, CURRENT_TIMESTAMP)),
    ('seed-run-004', 'ingest_orders', 'SUCCESS', 100,  NULL,   NULL,                         DATEADD('minute', -15, CURRENT_TIMESTAMP), DATEADD('minute', -14, CURRENT_TIMESTAMP)),
    ('seed-run-005', 'ingest_orders', 'SUCCESS', 750,  NULL,   NULL,                         DATEADD('minute',  -5, CURRENT_TIMESTAMP), DATEADD('minute',  -4, CURRENT_TIMESTAMP))
AS t(RUN_ID, PROC_NAME, STATUS, ROWS_LOADED, ERROR_CODE, ERROR_MSG, STARTED_AT, ENDED_AT);

-- Seed a small batch of ORDERS matching seed-run-001
INSERT INTO ORDERS (ORDER_ID, RUN_ID, CUSTOMER_ID, AMOUNT, REGION, ORDER_TS)
SELECT
    UUID_STRING(),
    'seed-run-001',
    UNIFORM(1, 1000, RANDOM())::NUMBER,
    ROUND(UNIFORM(10.0, 999.0, RANDOM())::FLOAT, 2),
    ['NA', 'EMEA', 'APAC', 'LATAM'][UNIFORM(0, 3, RANDOM())],
    DATEADD('second', -UNIFORM(0, 3600, RANDOM()), CURRENT_TIMESTAMP)
FROM TABLE(GENERATOR(ROWCOUNT => 50));
