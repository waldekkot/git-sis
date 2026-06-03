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
  lib/config.py           # table FQNs (env-overridable for test isolation)
  .streamlit/config.toml  # Snowflake theme
  pyproject.toml          # SiS container runtime dependency file (required)
deploy/00_setup_env.sql   # idempotent schema + tables (CREATE OR ALTER)
deploy/10_git_and_streamlit.sql  # API integration + git repo + CREATE STREAMLIT FROM
deploy/99_cleanup.sql     # tear down all demo objects
scripts/                  # shell runner scripts (--help / --version on all)
  setup.sh                # create schema + tables
  run-local.sh            # launch app locally
  deploy.sh               # redeploy loop (--bootstrap for first run)
  verify.sh               # check live app + print URL (--open to launch browser)
tests/
  unit/                   # 13 tests, no Snowflake needed (CI)
  integration/            # 10 tests, real Snowflake (local only)
.github/workflows/ci.yml  # runs unit tests + ruff on every push
```

## Shell runners (--help / --version on all)

```bash
scripts/setup.sh                          # create schema + tables
scripts/run-local.sh                      # run app locally (default port 8501)
scripts/run-local.sh -p 8533             # custom port
scripts/deploy.sh                         # redeploy after git push
scripts/deploy.sh --bootstrap             # first-time wiring + deploy
scripts/verify.sh                         # show object + URL
scripts/verify.sh --open                  # open URL in browser
```

## Tests

Three-tier dev loop matching the app: local (no SF) → GitHub CI → real Snowflake.

```bash
# Tier 1 -- unit tests, no Snowflake, zero credentials
uv run pytest tests/unit/ -v

# Tier 2 -- GitHub Actions runs unit tests automatically on every push
# (see .github/workflows/ci.yml)

# Tier 3 -- integration tests against real Snowflake (temp schema, auto-cleaned)
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/integration/ -v
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
git push && scripts/deploy.sh            # shell runner wraps fetch + recreate + add live version
```

Or manually:
```bash
git push
snow sql -c oregon-sedemo -q "ALTER GIT REPOSITORY SNOWFLAKE_LEARNING_DB.GIT_SIS.APP_REPO FETCH"
# then re-run section 3 of deploy/10_git_and_streamlit.sql (CREATE OR REPLACE + ADD LIVE VERSION)
```

## Cleanup (remove all demo objects)

```bash
snow sql -c oregon-sedemo -f deploy/99_cleanup.sql
```

## Target

Connection `oregon-sedemo` (account `sfseeurope-wkot_demo1`),
`SNOWFLAKE_LEARNING_DB.GIT_SIS`, warehouse `COMPUTE_WH`, compute pool
`SYSTEM_COMPUTE_POOL_CPU`.
