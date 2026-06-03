# git-sis: Streamlit-in-Snowflake ingestion console

A local-first Streamlit + Snowpark **ingestion ops console**, deployed to
Snowflake as a **Streamlit-in-Snowflake (SiS)** app on the **container runtime**,
developed via **Snowsight Workspaces** and automated through GitHub Actions.

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
lib/
  _lib.sh                  # shared helpers sourced by all scripts (--help/--version/-c)
app/                       # Streamlit app root
  streamlit_app.py         # entry point (MAIN_FILE)
  snowflake.yml            # Workspace + CLI deploy config (snow streamlit deploy)
  pyproject.toml           # container runtime dependencies
  pages/                   # run history, error explorer
  lib/session.py           # local/SiS session seam
  lib/ingest.py            # Snowpark ingestion + logging + error handling
  lib/config.py            # table FQNs (env-overridable for test isolation)
  .streamlit/config.toml   # Snowflake theme
deploy/
  01_setup_infra.sql       # one-time: GIT_SIS_INFRA DB + SECRETS schema
  00_setup_env.sql         # idempotent: GIT_SIS schema + ORDERS + INGEST_LOG
  10_git_and_streamlit.sql # optional: git wiring (API integration + GIT REPOSITORY)
  98_cleanup_infra.sql     # nuclear teardown: drops GIT_SIS_INFRA + PAT secret
  99_cleanup.sql           # reset: drops GIT_SIS schema (keeps GIT_SIS_INFRA)
scripts/                   # numbered runners — logical step-by-step workflow
  10_setup.sh              # one-time env setup (--with-git for git wiring)
  20_run-local.sh          # local dev loop
  30_deploy.sh             # deploy to SiS via snow streamlit deploy
  40_verify.sh             # confirm app live + print URL (--open to launch browser)
  90_cleanup.sh            # reset demo (keeps PAT secret)
  99_cleanup-infra.sh      # full teardown (drops everything, --yes to skip prompt)
tests/
  unit/                    # 35 tests, no Snowflake needed (CI) — 100% coverage
  integration/             # 10 tests, real Snowflake (local only)
.pre-commit-config.yaml    # ruff lint+format, ty type check, pytest unit
.github/workflows/ci.yml   # unit tests on every push; snow streamlit deploy on main
docs/tutorial/             # interactive HTML tutorial (6 pages, animated SVGs)
```

## Workspaces (interactive development)

Open `app/` in a Snowsight Workspace for a browser-based development experience:

1. **Snowsight → Workspaces → New workspace**
2. Connect to `https://github.com/waldekkot/git-sis` (optional, for git-sync)
3. Navigate to `app/streamlit_app.py` → press **Run** for a private dev preview
4. Press **Deploy** to publish using settings from `app/snowflake.yml`

The workspace reads `app/snowflake.yml` for compute pool, runtime, and EAI settings.
Code changes stay private until you deploy.

## Shell runners (numbered, --help / --version on all)

```bash
# --- First-time setup ---
scripts/10_setup.sh                           # infra DB + GIT_SIS schema + tables
scripts/10_setup.sh --with-git               # also wire GIT REPOSITORY for workspace git-sync

# --- Dev loop ---
scripts/20_run-local.sh                       # run app locally (default port 8501)
scripts/20_run-local.sh -p 8533              # custom port

# --- Deploy ---
scripts/30_deploy.sh                          # deploy via snow streamlit deploy
scripts/30_deploy.sh -c my-prod-conn         # different connection

# --- Verify ---
scripts/40_verify.sh                          # show object status + URL
scripts/40_verify.sh --open                   # open URL in browser

# --- Cleanup ---
scripts/90_cleanup.sh                         # reset demo (keeps infra DB + PAT)
scripts/99_cleanup-infra.sh                   # full teardown (prompts for confirmation)
scripts/99_cleanup-infra.sh --yes             # skip confirmation (for scripted use)
```

## GitHub PAT secret (one-time, permanent)

The GitHub PAT lives in **`GIT_SIS_INFRA.SECRETS.GITHUB_PAT`** — a separate
database that survives `90_cleanup.sh` resets. It is only needed if you use
`--with-git` (workspace git-sync) or the legacy git-FROM deploy approach.

```bash
# After scripts/10_setup.sh, create the secret once:
snow sql -c oregon-sedemo -q "
  CREATE OR REPLACE SECRET GIT_SIS_INFRA.SECRETS.GITHUB_PAT
      TYPE = PASSWORD
      USERNAME = 'waldekkot'
      PASSWORD = '<your-classic-github-pat>';"
```

## Run it

```bash
# 0. Install deps + pre-commit hooks
uv sync && uv run pre-commit install

# 1. One-time: create infra DB + GIT_SIS schema + tables
scripts/10_setup.sh -c oregon-sedemo

# 2. Verify locally (uses CLI connection via the session seam)
scripts/20_run-local.sh -c oregon-sedemo

# 3. Deploy to SiS (workspace-native: uploads app/ files via snow streamlit deploy)
scripts/30_deploy.sh -c oregon-sedemo

# 4. Confirm app is live
scripts/40_verify.sh --open -c oregon-sedemo
```

## Workspace alternative

After step 1, open `app/` in Snowsight Workspace → **Run** (private preview) → **Deploy**.
This uses `app/snowflake.yml` for the same compute pool and runtime settings.

## Redeploy after a change

```bash
# CLI (same as CI): uploads current app/ to Snowflake stage
git push && scripts/30_deploy.sh

# Or deploy from Snowsight workspace: open → Deploy
```

## Tests

Three-tier dev loop: local (no SF) → GitHub CI → real Snowflake.

```bash
# Tier 1 -- unit tests using Snowflake's local testing framework (100% coverage, ~1s)
# Ref: https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally
uv run pytest tests/unit/ -v

# Tier 2 -- GitHub Actions runs unit tests + coverage check on every push
# (see .github/workflows/ci.yml)

# Tier 3 -- integration tests against real Snowflake (temp schema, auto-cleaned, ~60s)
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/integration/ -v

# Cross-validate unit tests against real Snowflake:
SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo uv run pytest tests/unit/ -v --snowflake-session=live
```

Coverage is enforced at 80% minimum (`--cov-fail-under=80` in `pyproject.toml`).
Unit tests currently achieve **100%** across `app/lib/` and `app/streamlit_app.py`.

**Local testing framework:** `ingest.py` uses the DataFrame API exclusively
(no `session.sql()`) so the emulator runs all logic in-process. `uniform` and `round`
Snowflake built-ins are provided via `@snowflake.snowpark.mock.patch` in `tests/unit/conftest.py`.

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
| `unit-tests` | push + PR | ruff lint + 35 unit tests + 100% coverage check |
| `deploy-to-sis` | push to `main` only | `snow streamlit deploy` after unit-tests pass |

The deploy job runs `scripts/30_deploy.sh -c ci` which executes
`snow streamlit deploy -p app/ --replace` — workspace-native, no GIT REPOSITORY FETCH needed.

### Setting up the `SF_PAT_TOKEN` secret (one-time)

1. Read your Snowflake PAT token value (local token file for `oregon-sedemo`)
2. **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `SF_PAT_TOKEN`, Value: the raw token string

## Cleanup

| Script | What it removes | PAT secret |
|--------|----------------|------------|
| `scripts/90_cleanup.sh` | GIT_SIS schema, API integration, STREAMLIT | **Survives** |
| `scripts/99_cleanup-infra.sh` | Everything + GIT_SIS_INFRA DB + GITHUB_PAT | **Dropped** |

```bash
# Normal reset (keep the PAT — no re-entry needed on rebuild)
scripts/90_cleanup.sh -c oregon-sedemo

# Full decommission (requires confirmation or --yes)
scripts/99_cleanup-infra.sh -c oregon-sedemo
```

## Target

Connection `oregon-sedemo` (account `sfseeurope-wkot_demo1`),
`SNOWFLAKE_LEARNING_DB.GIT_SIS`, warehouse `COMPUTE_WH`, compute pool
`SYSTEM_COMPUTE_POOL_CPU`.
