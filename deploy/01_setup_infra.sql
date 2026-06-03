-- =====================================================================
-- 01_setup_infra.sql  -- one-time infra: database and schema for the
--                        GitHub PAT secret (survives 99_cleanup.sql)
-- =====================================================================
-- This database lives OUTSIDE the GIT_SIS demo schema so that running
-- 99_cleanup.sql (which drops SNOWFLAKE_LEARNING_DB.GIT_SIS CASCADE)
-- never destroys the GitHub PAT credential.
--
-- Run ONCE before the first bootstrap:
--   snow sql -c oregon-sedemo -f deploy/01_setup_infra.sql
--
-- Then create the secret out-of-band (value never stored in git):
--   snow sql -c oregon-sedemo -q "
--     CREATE OR REPLACE SECRET GIT_SIS_INFRA.SECRETS.GITHUB_PAT
--         TYPE = PASSWORD
--         USERNAME = 'waldekkot'
--         PASSWORD = '<your-classic-github-pat>';"
--
-- Idempotent: safe to re-run.
-- =====================================================================

USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS GIT_SIS_INFRA
    COMMENT = 'Infrastructure DB for git-sis demo: holds permanent credentials that survive demo cleanup.';

CREATE SCHEMA IF NOT EXISTS GIT_SIS_INFRA.SECRETS
    COMMENT = 'GitHub PAT and other long-lived secrets for the git-sis demo.';

SELECT
    'Infra setup complete' AS STATUS,
    CURRENT_ROLE()         AS ROLE,
    'GIT_SIS_INFRA.SECRETS.GITHUB_PAT -- create this secret out-of-band with your GitHub PAT'
        AS NEXT_STEP;
