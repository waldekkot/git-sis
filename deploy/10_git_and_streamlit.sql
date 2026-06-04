-- =====================================================================
-- 10_git_and_streamlit.sql  -- git-connected SiS deploy (container runtime)
-- =====================================================================
-- Wires Snowflake to the GitHub repo via OAuth2 (Snowflake GitHub App)
-- and creates the Streamlit object directly FROM the git repository clone,
-- on the container runtime.
--
-- Authentication: Snowflake GitHub App OAuth2
--   No secrets, no PATs, no rotation.  Each developer authorizes once in
--   Snowsight; Snowflake manages the OAuth tokens automatically.
--
-- Run order matters. Sections 1-2 are a ONE-TIME bootstrap (idempotent).
-- Section 3 is the (re)deploy loop -- safe to re-run after every git push.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. API integration (needs ACCOUNTADMIN).
--    Uses the Snowflake GitHub App -- no client-id, secret, or redirect
--    URI registration required.  The App is pre-configured by Snowflake.
-- ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE API INTEGRATION IF NOT EXISTS git_api_waldekkot
    API_PROVIDER = git_https_api
    API_ALLOWED_PREFIXES = ('https://github.com/waldekkot')
    API_USER_AUTHENTICATION = (TYPE = SNOWFLAKE_GITHUB_APP)
    ENABLED = TRUE;

GRANT USAGE ON INTEGRATION git_api_waldekkot TO ROLE SYSADMIN;

-- ---------------------------------------------------------------------
-- 2. OAuth authorization (one-time, per user).
--    Before the first FETCH each user must authorize the Snowflake GitHub
--    App.  Open Snowsight → Projects → any Workspace → Files tab →
--    "Connect Git Repository" and complete the GitHub OAuth flow.
--    After that one authorization, FETCH works from Snowsight AND the CLI.
-- ---------------------------------------------------------------------

-- ---------------------------------------------------------------------
-- 3. (Re)deploy loop -- SYSADMIN. Safe to re-run after every git push.
-- ---------------------------------------------------------------------
USE ROLE SYSADMIN;
USE SCHEMA SNOWFLAKE_LEARNING_DB.GIT_SIS;

-- No GIT_CREDENTIALS parameter: authentication is handled by the
-- Snowflake GitHub App OAuth2 integration above.
CREATE GIT REPOSITORY IF NOT EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO
    API_INTEGRATION = git_api_waldekkot
    ORIGIN = 'https://github.com/waldekkot/git-sis';

-- Pull the latest commit(s) into the clone.
-- Requires OAuth authorization (Section 2 above) to be completed first.
ALTER GIT REPOSITORY SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO FETCH;

-- Create the app FROM the git clone, container runtime.
-- NOTE: container runtime requires app/pyproject.toml + PYPI_ACCESS_INTEGRATION.
--   Grant first (as ACCOUNTADMIN):
--     GRANT USAGE ON INTEGRATION PYPI_ACCESS_INTEGRATION TO ROLE SYSADMIN;
CREATE OR REPLACE STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE
    FROM '@SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO/branches/main/app/'
    MAIN_FILE = 'streamlit_app.py'
    QUERY_WAREHOUSE = COMPUTE_WH
    RUNTIME_NAME = 'SYSTEM$ST_CONTAINER_RUNTIME_PY3_11'
    COMPUTE_POOL = SYSTEM_COMPUTE_POOL_CPU
    EXTERNAL_ACCESS_INTEGRATIONS = (PYPI_ACCESS_INTEGRATION)
    TITLE = 'Ingestion Ops Console';

-- Make it live (required before headless EXECUTE STREAMLIT / first view).
ALTER STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE ADD LIVE VERSION FROM LAST;

SHOW STREAMLITS LIKE 'INGEST_CONSOLE' IN SCHEMA SNOWFLAKE_LEARNING_DB.GIT_SIS;
