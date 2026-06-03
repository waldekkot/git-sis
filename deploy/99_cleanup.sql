-- =====================================================================
-- 99_cleanup.sql  -- reset the demo (keeps the GitHub PAT secret)
-- =====================================================================
-- Drops everything in dependency order (children first, then parents).
-- Idempotent: IF EXISTS on every statement -- safe to re-run.
--
-- Cleanup levels:
--   99_cleanup.sql (this)  -- resets demo state; PAT secret survives
--   98_cleanup_infra.sql   -- FULL teardown including GIT_SIS_INFRA DB
--
-- Run:
--   snow sql -c oregon-sedemo -f deploy/99_cleanup.sql
--
-- WARNING: This is destructive and irreversible for GIT_SIS data.
-- =====================================================================

-- -----------------------------------------------------------------
-- 1. Schema-level objects (SYSADMIN is the owner)
-- -----------------------------------------------------------------
USE ROLE SYSADMIN;

-- Streamlit app
DROP STREAMLIT IF EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE;

-- Git repository clone (also releases the external git connection)
DROP GIT REPOSITORY IF EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO;

-- NOTE: GITHUB_PAT is NOT dropped here -- it lives in a separate database
-- (GIT_SIS_INFRA.SECRETS.GITHUB_PAT) so it survives demo resets.
-- To also drop the credential, run: deploy/98_cleanup_infra.sql

-- Tables + the schema itself (CASCADE drops ORDERS, INGEST_LOG, and anything else)
DROP SCHEMA IF EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS CASCADE;

-- -----------------------------------------------------------------
-- 2. Account-level integration (needs ACCOUNTADMIN)
--    Remove only if no other Git repositories on this account use it.
-- -----------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

REVOKE USAGE ON INTEGRATION git_api_waldekkot FROM ROLE SYSADMIN;
DROP API INTEGRATION IF EXISTS git_api_waldekkot;

-- NOTE: PYPI_ACCESS_INTEGRATION is a shared, pre-existing integration.
--       It is intentionally NOT dropped here.

-- -----------------------------------------------------------------
-- 3. Verify clean state
-- -----------------------------------------------------------------
USE ROLE SYSADMIN;
SELECT
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.SCHEMATA
     WHERE SCHEMA_NAME = 'GIT_SIS' AND CATALOG_NAME = 'SNOWFLAKE_LEARNING_DB') AS GIT_SIS_SCHEMA_EXISTS,
    'Cleanup complete -- GIT_SIS_SCHEMA_EXISTS should be 0' AS STATUS;
