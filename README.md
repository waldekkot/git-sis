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
deploy/01_setup_infra.sql # one-time: create GIT_SIS_INFRA DB + SECRETS schema
deploy/00_setup_env.sql   # idempotent schema + tables (CREATE OR ALTER)
deploy/10_git_and_streamlit.sql  # API integration + git repo + CREATE STREAMLIT FROM
deploy/98_cleanup_infra.sql  # nuclear teardown: drops GIT_SIS_INFRA + PAT secret
deploy/99_cleanup.sql     # reset demo state (keeps GIT_SIS_INFRA + PAT secret)
scripts/                  # shell runner scripts (--help / --version on all)
  setup.sh                # create infra DB + schema + tables
  run-local.sh            # launch app locally
  deploy.sh               # redeploy loop (--bootstrap for first run)
  verify.sh               # check live app + print URL (--open to launch browser)
tests/
  unit/                   # 24 tests, no Snowflake needed (CI) — 100% coverage
  integration/            # 10 tests, real Snowflake (local only)
.pre-commit-config.yaml   # ruff lint+format, ty type check, pytest unit
.github/workflows/ci.yml  # unit tests + ruff on every push; SiS redeploy on main
docs/tutorial/            # interactive HTML tutorial (6 pages, animated SVGs)
```

## GitHub PAT secret (one-time setup, permanent)

The GitHub PAT is stored in **`GIT_SIS_INFRA.SECRETS.GITHUB_PAT`** — a separate
database from the demo schema. It survives `99_cleanup.sql` resets, so you only
create it once.

```bash
# Step 1: create the infra database + secrets schema (idempotent)
snow sql -c oregon-sedemo -f deploy/01_setup_infra.sql

# Step 2: store your GitHub PAT (classic PAT, repo scope) — run once ever
snow sql -c oregon-sedemo -q "
  CREATE OR REPLACE SECRET GIT_SIS_INFRA.SECRETS.GITHUB_PAT
      TYPE = PASSWORD
      USERNAME = 'waldekkot'
      PASSWORD = '<your-classic-github-pat>';"
```

After this, every `scripts/deploy.sh --bootstrap` and every `99_cleanup.sql` +
rebuild cycle works without touching the credential.

## Shell runners (--help / --version on all)

```bash
scripts/setup.sh                          # create infra DB + schema + tables
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
# Tier 1 -- unit tests using Snowflake's local testing framework (100% coverage, ~1s)
# Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally
uv run pytest tests/unit/ -v

# Tier 2 -- GitHub Actions runs unit tests + coverage check on every push
# (see .github/workflows/ci.yml)

# Tier 3 -- integration tests against real Snowflake (temp schema, auto-cleaned, ~55s)
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/integration/ -v

# Unit tests can also run against real Snowflake for cross-validation:
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/unit/ -v --snowflake-session=live
```

Coverage is enforced at 80% minimum (`--cov-fail-under=80` in `pyproject.toml`).
Unit tests currently achieve **100%** across `app/lib/` and `app/streamlit_app.py`.

**Local testing framework:** `ingest.py` uses the DataFrame API exclusively
(no `session.sql()`) so the emulator runs all logic in-process. `uniform` and `round`
Snowflake built-ins are provided via `@snowflake.snowpark.mock.patch` in `tests/unit/conftest.py`.

## Run it

```bash
# 0. deps
uv sync && uv run pre-commit install

# 1. one-time infra setup (creates GIT_SIS_INFRA database for the PAT secret)
snow sql -c oregon-sedemo -f deploy/01_setup_infra.sql

# 2. create your GitHub PAT secret (one-time ever -- survives cleanup)
snow sql -c oregon-sedemo -q "CREATE OR REPLACE SECRET GIT_SIS_INFRA.SECRETS.GITHUB_PAT ..."

# 3. create DEV schema + tables
snow sql -c oregon-sedemo -f deploy/00_setup_env.sql

# 4. verify locally (uses CLI connection via the session seam)
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run streamlit run app/streamlit_app.py

# 5. push to GitHub
git push -u origin main

# 6. bootstrap git wiring + deploy SiS (PAT already in GIT_SIS_INFRA)
scripts/deploy.sh --bootstrap -c oregon-sedemo

# 7. open the app
scripts/verify.sh --open -c oregon-sedemo
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

## Pre-commit Hooks

Quality gates on every `git commit`: ruff lint + format, ty type check, unit tests.

```bash
# One-time setup (after uv sync)
uv run pre-commit install

# Run manually against all files
uvx pre-commit run --all-files
```

Hooks run in order: `trailing-whitespace` → `ruff check --fix` → `ruff format` → `ty check app/lib/` → `pytest tests/unit/ -q`.
Commits are blocked until all hooks pass. The ruff hook auto-fixes lint issues and re-stages them.

## CI/CD

GitHub Actions runs on every push and pull request:

| Job | Trigger | What it does |
|-----|---------|--------------|
| `unit-tests` | push + PR | ruff lint + 24 unit tests + 100% coverage check |
| `deploy-to-sis` | push to `main` only | Redeploys SiS app after unit-tests pass |

### Setting up the `SF_PAT_TOKEN` secret (one-time)

The SiS deploy job authenticates to Snowflake using a Programmatic Access Token.

1. Read your PAT token value (local token file for `oregon-sedemo`)
2. In your GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `SF_PAT_TOKEN`, Value: the raw token string

The CI connection targets `sfseeurope-wkot_demo1` as user `wkot` with `PROGRAMMATIC_ACCESS_TOKEN` auth.

## Cleanup

| Script | What it removes | PAT secret |
|--------|----------------|------------|
| `deploy/99_cleanup.sql` | STREAMLIT, GIT REPOSITORY, GIT_SIS schema, API integration | **Survives** (in GIT_SIS_INFRA) |
| `deploy/98_cleanup_infra.sql` | GIT_SIS_INFRA database + GITHUB_PAT secret | **Dropped** (nuclear option) |

```bash
# Normal reset (keep the PAT -- next bootstrap needs no re-entry)
snow sql -c oregon-sedemo -f deploy/99_cleanup.sql

# Full decommission (run 99 first, then 98, or run 98 alone)
snow sql -c oregon-sedemo -f deploy/98_cleanup_infra.sql
```

## Target

Connection `oregon-sedemo` (account `sfseeurope-wkot_demo1`),
`SNOWFLAKE_LEARNING_DB.GIT_SIS`, warehouse `COMPUTE_WH`, compute pool
`SYSTEM_COMPUTE_POOL_CPU`.
Credentials: `GIT_SIS_INFRA.SECRETS.GITHUB_PAT` (permanent, survives demo resets).
