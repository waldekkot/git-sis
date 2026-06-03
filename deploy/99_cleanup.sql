-- =====================================================================
-- 99_cleanup.sql  -- tear down ALL objects created by this demo
-- =====================================================================
-- Drops everything in dependency order (children first, then parents).
-- Idempotent: IF EXISTS on every statement -- safe to re-run.
--
-- Run:
--   snow sql -c oregon-sedemo -f deploy/99_cleanup.sql
--
-- WARNING: This is destructive and irreversible.  Only run it when you
-- are done with the demo.  It will DELETE all data in GIT_SIS.
-- =====================================================================

-- -----------------------------------------------------------------
-- 1. Schema-level objects (SYSADMIN is the owner)
-- -----------------------------------------------------------------
USE ROLE SYSADMIN;

-- Streamlit app
DROP STREAMLIT IF EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE;

-- Git repository clone (also releases the external git connection)
DROP GIT REPOSITORY IF EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO;

-- GitHub PAT secret
DROP SECRET IF EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.GITHUB_PAT;

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
