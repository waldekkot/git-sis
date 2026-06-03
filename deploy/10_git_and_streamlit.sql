-- =====================================================================
-- 10_git_and_streamlit.sql  -- git-connected SiS deploy (container runtime)
-- =====================================================================
-- Wires Snowflake to the private GitHub repo and creates the Streamlit object
-- directly FROM the git repository clone, on the container runtime.
--
-- Run order matters. Sections 1-2 are a ONE-TIME bootstrap (idempotent).
-- Section 3 is the (re)deploy loop -- safe to re-run after every git push.
--
-- IMPORTANT: never commit a real PAT. The secret below uses a placeholder;
-- create it once out-of-band with the real token, e.g.:
--   snow sql -c oregon-sedemo -q "CREATE SECRET IF NOT EXISTS \
--     SNOWFLAKE_LEARNING_DB.GIT_SIS.GITHUB_PAT TYPE=PASSWORD \
--     USERNAME='waldekkot' PASSWORD='<REAL_PAT>'"
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Secret with the GitHub PAT (SYSADMIN owns the schema -> can create).
--    One-time bootstrap. Replace the placeholder OR create out-of-band (above).
-- ---------------------------------------------------------------------
USE ROLE SYSADMIN;
USE SCHEMA SNOWFLAKE_LEARNING_DB.GIT_SIS;

CREATE SECRET IF NOT EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.GITHUB_PAT
    TYPE = PASSWORD
    USERNAME = 'waldekkot'
    PASSWORD = '<<PUT_GITHUB_PAT_HERE>>';   -- fine-grained PAT, Contents:read

-- ---------------------------------------------------------------------
-- 2. API integration for github.com/waldekkot (needs ACCOUNTADMIN).
--    If your role lacks CREATE INTEGRATION, hand this block to an admin.
-- ---------------------------------------------------------------------
USE ROLE ACCOUNTADMIN;

CREATE API INTEGRATION IF NOT EXISTS git_api_waldekkot
    API_PROVIDER = git_https_api
    API_ALLOWED_PREFIXES = ('https://github.com/waldekkot')
    ALLOWED_AUTHENTICATION_SECRETS = (SNOWFLAKE_LEARNING_DB.GIT_SIS.GITHUB_PAT)
    ENABLED = TRUE;

GRANT USAGE ON INTEGRATION git_api_waldekkot TO ROLE SYSADMIN;

-- ---------------------------------------------------------------------
-- 3. (Re)deploy loop -- SYSADMIN. Safe to re-run after every git push.
-- ---------------------------------------------------------------------
USE ROLE SYSADMIN;
USE SCHEMA SNOWFLAKE_LEARNING_DB.GIT_SIS;

CREATE GIT REPOSITORY IF NOT EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO
    API_INTEGRATION = git_api_waldekkot
    GIT_CREDENTIALS = SNOWFLAKE_LEARNING_DB.GIT_SIS.GITHUB_PAT
    ORIGIN = 'https://github.com/waldekkot/git-sis';

-- Pull the latest commit(s) into the clone (FROM snapshots at CREATE time).
ALTER GIT REPOSITORY SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO FETCH;

-- Create the app FROM the git clone, container runtime. ROOT_LOCATION is NOT
-- valid for container runtime -- FROM is required (and supports git integration).
-- NOTE: the container runtime REQUIRES a dependency file (app/pyproject.toml) in
-- the app source dir, and EXTERNAL_ACCESS_INTEGRATIONS with a PyPI EAI to resolve
-- it. Without app/pyproject.toml the app fails to load:
--   "Installing dependencies failed because the pyproject.toml file does not exist."
-- Grant the PyPI EAI to SYSADMIN first (as ACCOUNTADMIN):
--   GRANT USAGE ON INTEGRATION PYPI_ACCESS_INTEGRATION TO ROLE SYSADMIN;
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
