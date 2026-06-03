-- =====================================================================
-- 98_cleanup_infra.sql  -- FULL teardown including the infra database
-- =====================================================================
-- ⚠  NUCLEAR OPTION: only run when completely decommissioning the demo.
--
-- For a normal "reset the demo" use 99_cleanup.sql instead, which keeps
-- the GIT_SIS_INFRA database and your GitHub PAT secret intact.
--
-- Run:
--   snow sql -c oregon-sedemo -f deploy/98_cleanup_infra.sql
--
-- Cleanup order:
--   98_cleanup_infra.sql  (this file)  -- drops the infra DB + PAT secret
--   99_cleanup.sql                     -- drops GIT_SIS schema + API integration
--
-- Or run 99_cleanup.sql first, then this file.  Both are idempotent.
-- =====================================================================

USE ROLE SYSADMIN;

-- The GitHub PAT credential
DROP SECRET IF EXISTS GIT_SIS_INFRA.SECRETS.GITHUB_PAT;

-- The secrets schema
DROP SCHEMA IF EXISTS GIT_SIS_INFRA.SECRETS CASCADE;

-- The infra database
DROP DATABASE IF EXISTS GIT_SIS_INFRA;

SELECT
    'Infra cleanup complete' AS STATUS,
    'GIT_SIS_INFRA database and all its contents have been dropped' AS NOTE;
