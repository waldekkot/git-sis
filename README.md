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
  00_setup_env.sql         # idempotent: GIT_SIS schema + ORDERS + INGEST_LOG
  10_git_and_streamlit.sql # optional: git wiring (OAuth2 API integration + GIT REPOSITORY)
  99_cleanup.sql           # full teardown: drops GIT_SIS schema + API integration
scripts/                   # numbered runners — logical step-by-step workflow
  10_setup.sh              # one-time env setup (--with-git for git wiring)
  20_run-local.sh          # local dev loop
  30_deploy.sh             # deploy to SiS via snow streamlit deploy
  40_verify.sh             # confirm app live + print URL (--open to launch browser)
  90_cleanup.sh            # reset demo (drops GIT_SIS schema + API integration)
  99_cleanup-infra.sh      # full teardown (drops everything, --yes to skip prompt)
tests/
  unit/                    # 37 tests, no Snowflake needed (CI) — 100% coverage
    conftest.py            # seeded_session, uuid_patch, shared schemas, mock patches
    test_app.py            # UI tests via Streamlit AppTest + Snowpark emulator
    test_ingest.py         # data layer tests via Snowpark local testing
    test_session.py        # session seam tests (mocks justified here)
  integration/             # 10 tests, real Snowflake (local only)
Makefile                   # make test / dev / deploy / clean and more
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
scripts/10_setup.sh                           # GIT_SIS schema + tables
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
scripts/90_cleanup.sh                         # reset demo
scripts/99_cleanup-infra.sh                   # full teardown (prompts for confirmation)
scripts/99_cleanup-infra.sh --yes             # skip confirmation (for scripted use)
```

## GitHub App OAuth authorization (one-time, per user)

When you use `--with-git` (workspace git-sync or `make deploy-git`), Snowflake
authenticates to GitHub via the **Snowflake GitHub App** OAuth2 flow.
No PAT, no client secret, no rotation — Snowflake manages the tokens.

After running `scripts/10_setup.sh --with-git`:

1. Open **Snowsight → Projects → any Workspace**
2. In the **Files** tab select **Connect Git Repository**
3. Complete the GitHub OAuth authorization (one click)

That's it. Subsequent `FETCH` operations (including `make deploy-git`) work
automatically from both Snowsight and the CLI.

## Run it

```bash
# 0. Install deps + pre-commit hooks (no Snowflake needed)
make install

# Optional: configure direnv for automatic connection switching (recommended)
cp .envrc.example .envrc   # edit SNOWFLAKE_DEFAULT_CONNECTION_NAME + schema vars
direnv allow               # loads env vars automatically when you cd into this dir

# 1. One-time: create GIT_SIS schema + tables
scripts/10_setup.sh

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

## Development workflow (TDD)

### The three-ring testing model

```
 ┌─────────────────────────────────────────────┐
 │  Ring 1 — local, 0 credentials, ~2s        │
 │  Snowpark local testing + Streamlit AppTest │
 │  make test    (TDD inner loop)              │
 └─────────────────────────────────────────────┘
         ↓  passes? push
 ┌─────────────────────────────────────────────┐
 │  Ring 2 — GitHub Actions CI               │
 │  Same unit tests; snow streamlit deploy    │
 │  on main branch                            │
 └─────────────────────────────────────────────┘
         ↓  deploy done? verify in Snowflake
 ┌─────────────────────────────────────────────┐
 │  Ring 3 — real Snowflake, ~60s            │
 │  Integration tests (temp schema)           │
 │  make test-integration                     │
 │  make test-live  (cross-validate unit)     │
 └─────────────────────────────────────────────┘
```

### TDD inner loop (`make test`, ~2s)

1. Write a failing test in `tests/unit/`
2. `make test` — red
3. Implement the minimum code to pass
4. `make test` — green
5. Refactor. `make test` stays green.
6. Before push: `make test-full` (~60s, exercises real Snowflake)

### What to mock and why

The goal is **zero MagicMock for business logic**. Use these patterns instead:

| Need | Pattern | Why |
|------|---------|-----|
| Snowpark session backend | `seeded_session` fixture (local testing emulator) | Real DataFrames, real rows, no credentials |
| UUID_STRING built-in | `uuid_patch` fixture (`@snowflake.snowpark.mock.patch`) | Emulator limitation; doesn't bypass logic |
| `uniform`, `round` built-ins | `@snowflake.snowpark.mock.patch` in conftest | Same: emulator gap, not business logic |
| Force a controlled failure | `MagicMock` in `test_warning_when_session_fails` | Only test that needs inaccessible tables |
| Session seam tests | `monkeypatch` + `unittest.mock` in `test_session.py` | Testing the seam itself, not Snowpark logic |

**Mock inventory principle:** mock only what the emulator cannot provide; inject what's configurable.

### The snowpark_app fixture (zero-mock UI tests)

AppTest combined with the local testing session gives end-to-end UI + data-layer tests:

```python
@pytest.fixture()
def snowpark_app(seeded_session, uuid_patch):  # uuid_patch is a context, not a param
    """AppTest backed by real Snowpark local testing session."""
    with patch("lib.session.get_session", return_value=seeded_session):
        at = AppTest.from_file(APP_FILE).run()
    return at, seeded_session

def test_button_click_writes_500_rows_to_orders(snowpark_app):
    at, sess = snowpark_app
    with patch("lib.session.get_session", return_value=sess):
        at.button[0].click().run()              # Streamlit UI interaction
    assert "500" in at.success[0].value         # UI assertion
    assert sess.table(_cfg.ORDERS_TABLE).count() == 500  # real Snowpark assertion
```

No MagicMock in the happy path. The emulator writes real rows; `count()` is real.

## Tests

Three-ring command reference:

```bash
# Ring 1 — TDD inner loop (Snowpark local testing + AppTest, ~2s)
make test                             # or: uv run pytest tests/unit/ -v

# Ring 1 — watch mode (re-runs on file save)
make test-watch

# Ring 2 — CI gate (same tests, runs in GitHub Actions)
# Triggered automatically on push/PR. See .github/workflows/ci.yml.

# Ring 3 — integration tests against real Snowflake (~60s)
make test-integration                 # needs SNOWFLAKE_DEFAULT_CONNECTION_NAME

# Ring 3 — cross-validate unit tests against real Snowflake
make test-live

# Full suite (unit + integration)
make test-full
```

Coverage is enforced at 80% minimum (`--cov-fail-under=80` in `pyproject.toml`).
Unit tests currently achieve **100%** across `app/lib/` and `app/streamlit_app.py`.

**Local testing framework:** `ingest.py` uses the DataFrame API exclusively
(no `session.sql()`) so the emulator runs all logic in-process. `uniform` and `round`
Snowflake built-ins are provided via `@snowflake.snowpark.mock.patch` in `tests/unit/conftest.py`.

## Makefile

All common developer commands in one place:

```bash
make install          # uv sync + pre-commit install (one-time setup)
make test             # fast unit tests (~2s, TDD inner loop)
make test-watch       # watch mode on unit tests
make test-full        # unit + integration
make test-live        # cross-validate units against real Snowflake
make dev              # start app locally (port 8501)
make setup            # one-time Snowflake setup (GIT_SIS schema + tables)
make deploy           # snow streamlit deploy
make verify           # check app + print URL
make open             # open app URL in browser
make clean            # reset demo
make clean-all        # full teardown
make lint             # ruff check + format check
make fmt              # auto-format with ruff
make typecheck        # ty check app/lib/
make hooks            # run all pre-commit hooks
make help             # list all targets with descriptions
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

GitHub Actions runs on every push and pull request. Auth is **secretless (OIDC /
Workload Identity Federation)** — no `SF_PAT_TOKEN`. See `docs/oidc-setup.md`.

| Job | Trigger | Environment | What it does |
|-----|---------|-------------|--------------|
| `unit-tests` | push + PR | — | ruff + 46 unit tests + 100% coverage + import-linter (`arch`) |
| `integration-tests` | push to `main` | `ci` | Snowpark integration tests in disposable schemas (OIDC) |
| `deploy-to-sis` | push to `main` | `prod` (approval) | `snow streamlit deploy` + post-deploy smoke check |
| `preview-deploy` | PR (non-fork) | `preview` | isolated `GIT_SIS_PR_<n>` app + URL comment |
| `release` | push tag `vX.Y.Z` | `prod` (approval) | deploy + `COMMIT VERSION` (rollback-able) — see `docs/runbook.md` |

### One-time setup (OIDC)

1. Run the SERVICE-user SQL in `docs/oidc-setup.md` (ACCOUNTADMIN).
2. Create GitHub Environments `ci`, `preview`, `prod` (set **required reviewers** on
   `prod` only).
3. There is **no token to store** — remove any legacy `SF_PAT_TOKEN` secret.

## Cleanup

| Script | What it removes |
|--------|------------------|
| `scripts/90_cleanup.sh` | GIT_SIS schema (CASCADE), STREAMLIT, GIT REPOSITORY, API integration |
| `scripts/99_cleanup-infra.sh` | Same as above, with a confirmation prompt (nuclear option) |

No separate infra database or PAT secret exists with OAuth2 —
both scripts drop the same objects.

```bash
# Normal reset
scripts/90_cleanup.sh

# Full decommission (requires confirmation or --yes)
scripts/99_cleanup-infra.sh
```

## Target

Connection `oregon-sedemo` (account `sfseeurope-wkot_demo1`),
`SNOWFLAKE_LEARNING_DB.GIT_SIS`, warehouse `COMPUTE_WH`, compute pool
`SYSTEM_COMPUTE_POOL_CPU`.
