# git-sis: Git-connected Streamlit-in-Snowflake ingestion console

A local-first Streamlit + Snowpark **ingestion ops console**, deployed to
Snowflake as a **git-connected** Streamlit-in-Snowflake (SiS) app on the
**container runtime** -- driven end-to-end from the `snow` CLI.

## What it does

- Generates synthetic orders with Snowpark and lands them in `ORDERS`.
- Logs every run to `INGEST_LOG` (`RUNNING -> SUCCESS/FAILED`) with structured
  error capture (errors are recorded and surfaced, never swallowed).
- Streamlit UI: KPIs, run history, error explorer, and an operator control to
  trigger a run (or force a failure to demo the error path).

## The "write once, run in two places" seam

`app/lib/session.py` is the only code that differs between laptop and SiS:
`get_active_session()` in SiS, a CLI-connection-built session locally. Verify
locally with confidence, then deploy unchanged.

## Layout

```
app/                      # SiS app root (FROM @repo/branches/main/app/)
  streamlit_app.py        # entry (MAIN_FILE)
  pages/                  # run history, error explorer
  lib/session.py          # local/SiS session seam
  lib/ingest.py           # Snowpark ingestion + logging + error handling
  lib/config.py           # table FQNs
  .streamlit/config.toml  # Snowflake theme
deploy/00_setup_env.sql   # idempotent schema + tables (CREATE OR ALTER)
deploy/10_git_and_streamlit.sql  # API integration + git repo + CREATE STREAMLIT FROM
```

## Run it

```bash
# 0. deps
uv sync

# 1. create DEV schema + tables (once)
snow sql -c oregon-sedemo -f deploy/00_setup_env.sql

# 2. verify locally (uses CLI connection via the session seam)
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run streamlit run app/streamlit_app.py

# 3. push to GitHub
git push -u origin main

# 4-5. bootstrap git wiring + deploy SiS (edit secret first, see file header)
snow sql -c oregon-sedemo -f deploy/10_git_and_streamlit.sql

# 6. headless smoke test
snow sql -c oregon-sedemo -q "EXECUTE STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE()"

# 7. open the app
snow streamlit get-url -c oregon-sedemo SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE
```

## Redeploy after a change

```bash
git push
snow sql -c oregon-sedemo -q "ALTER GIT REPOSITORY SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO FETCH"
# then re-run section 3 of deploy/10_git_and_streamlit.sql (CREATE OR REPLACE + ADD LIVE VERSION)
```

## Target

Connection `oregon-sedemo` (account `sfseeurope-wkot_demo1`),
`SNOWFLAKE_LEARNING_DB.GIT_SIS`, warehouse `COMPUTE_WH`, compute pool
`SYSTEM_COMPUTE_POOL_CPU`.
