# Makefile — common developer commands for git-sis
# Usage: make <target>   e.g. make test  or  make dev
#
# All Snowflake targets default to the connection named 'default' in
# ~/.snowflake/config.toml.  Override at any time:
#   make deploy CONN=my-other-conn
#   SNOWFLAKE_DEFAULT_CONNECTION_NAME=my-conn make dev
#
# Multi-environment deploy (env-var overrides for app/snowflake.yml):
#   make deploy GIT_SIS_DATABASE=PROD_DB GIT_SIS_SCHEMA=PROD_GIT_SIS CONN=prod
#   make deploy GIT_SIS_SCHEMA=GIT_SIS_PR_42 GIT_SIS_APP_NAME=INGEST_CONSOLE_PR_42
#
CONN ?= default
export SNOWFLAKE_DEFAULT_CONNECTION_NAME := $(CONN)

# Target database/schema/app — override to deploy to a different environment.
# These are forwarded as env vars to snow streamlit deploy, which picks them up
# via the <% ctx.env.VAR | default('...') %> expressions in app/snowflake.yml.
GIT_SIS_DATABASE ?= SNOWFLAKE_LEARNING_DB
GIT_SIS_SCHEMA   ?= GIT_SIS
GIT_SIS_APP_NAME ?= INGEST_CONSOLE
GIT_SIS_WAREHOUSE ?= COMPUTE_WH
export GIT_SIS_DATABASE GIT_SIS_SCHEMA GIT_SIS_APP_NAME GIT_SIS_WAREHOUSE

# Optional: pass --commit ALIAS to tag a stable version after deploying
# Usage: make deploy COMMIT=v1
COMMIT ?=

.PHONY: init install test test-watch test-watch-install test-xdist \
        test-full test-integration test-live \
        dev dev-port setup setup-git deploy deploy-git deploy-sql \
        verify open clean clean-all lint fmt typecheck arch hooks help

# -- First-time setup ----------------------------------------------------------

init:  ## One-command onboarding: deps + pre-commit + Snowflake schema
	@echo ""
	@echo "  git-sis — first-time setup"
	@echo "  ─────────────────────────────────────────"
	uv sync
	uv run pre-commit install
	@echo ""
	@echo "  Checking for a Snowflake connection named '$(CONN)' ..."
	@snow connection list 2>/dev/null | grep -q "$(CONN)" \
	    && echo "  [ok] Connection '$(CONN)' found." \
	    || (echo "  [warn] No connection named '$(CONN)' found." && \
	        echo "         Copy config.toml.example to ~/.snowflake/config.toml" && \
	        echo "         then run: snow connection add" && \
	        echo "  Skipping Snowflake setup until connection is configured." && exit 0)
	@echo ""
	scripts/10_setup.sh -c $(CONN)
	@echo ""
	@echo "  Setup complete. Try: make dev"
	@echo ""

install:  ## Install deps + pre-commit hooks (subset of init — skips schema setup)
	uv sync && uv run pre-commit install

# -- Testing -------------------------------------------------------------------

test:  ## Unit tests — module-scoped sessions (~2s) — TDD inner loop
	uv run pytest tests/unit/ -v --tb=short

test-watch:  ## Watch unit tests on file change (re-runs on save)
	uv run ptw tests/unit/ -- -x --tb=short --no-cov

test-xdist:  ## Parallel unit tests via xdist (use when suite grows past ~150 tests)
	# --dist=loadfile keeps module-scoped fixtures on the same worker.
	# At 46 tests xdist overhead exceeds the gain; re-evaluate around 150+ tests.
	uv run pytest tests/unit/ -v --tb=short -n auto --dist=loadfile

test-full:  ## Unit + integration tests against real Snowflake (~60s, needs credentials)
	uv run pytest tests/ -v --tb=short

test-integration:  ## Integration tests — parallel via xdist, ~12s (was ~60s serial)
	uv run pytest tests/integration/ -v --tb=short --no-cov -n auto

test-live:  ## Cross-validate unit tests against real Snowflake — parallel, ~80s
	uv run pytest tests/unit/ -v --tb=short --no-cov --snowflake-session=live -n auto --dist=loadfile

# -- Local development ---------------------------------------------------------

dev:  ## Start the app locally against real Snowflake (port 8501)
	scripts/20_run-local.sh -c $(CONN)

dev-port:  ## Start locally on a custom port: make dev-port PORT=8533
	scripts/20_run-local.sh -c $(CONN) -p $(PORT)

# -- Snowflake setup (one-time) ------------------------------------------------

setup:  ## Create infra DB + GIT_SIS schema + tables
	scripts/10_setup.sh -c $(CONN)

setup-git:  ## Setup + git wiring for Snowsight workspace git-sync and deploy-git / deploy-sql
	scripts/10_setup.sh -c $(CONN) --with-git

# -- Deploy --------------------------------------------------------------------

deploy:  ## Deploy to SiS via snow streamlit deploy (push-based, workspace-native)
	GIT_SIS_DATABASE=$(GIT_SIS_DATABASE) \
	GIT_SIS_SCHEMA=$(GIT_SIS_SCHEMA) \
	GIT_SIS_APP_NAME=$(GIT_SIS_APP_NAME) \
	GIT_SIS_WAREHOUSE=$(GIT_SIS_WAREHOUSE) \
	    scripts/30_deploy.sh -c $(CONN) $(if $(COMMIT),--commit $(COMMIT),)

deploy-git:  ## Pull-based deploy: fetch git repo → Snowflake reads branch tip (faster iteration)
	@# Prerequisite: make setup-git  (creates APP_REPO + API integration, one-time)
	@# Faster than push-based for rapid inner-loop iteration from Snowsight:
	@#   edit in workspace → Run (private preview) → this target updates the deployed app.
	@# Note: GIT REPOSITORY snapshots the branch at FETCH time; the app serves the new code
	@#       on next page load without a redeploy.
	snow sql -c $(CONN) -q \
	    "ALTER GIT REPOSITORY $(GIT_SIS_DATABASE).$(GIT_SIS_SCHEMA).APP_REPO FETCH;"
	@echo ""
	@echo "  [ok] Repository fetched. Open the app in Snowsight — it now serves the latest branch tip."
	@echo "       URL: make verify"
	@echo ""

deploy-sql:  ## Apply SQL infra scripts via snow git execute (pull-based DDL, requires setup-git)
	@# Runs deploy/00_setup_env.sql directly from the git repo object inside Snowflake.
	@# Prerequisite: make setup-git  (creates APP_REPO).
	@# Useful for applying schema changes without a local snow sql -f loop.
	snow git execute -c $(CONN) \
	    "@$(GIT_SIS_DATABASE).$(GIT_SIS_SCHEMA).APP_REPO/branches/main/deploy/00_setup_env.sql"

verify:  ## Check deployed app status + print URL
	scripts/40_verify.sh -c $(CONN)

open:  ## Open deployed app in browser
	scripts/40_verify.sh -c $(CONN) --open

# -- Cleanup -------------------------------------------------------------------

clean:  ## Reset demo (drops GIT_SIS schema, keeps infra DB + PAT)
	scripts/90_cleanup.sh -c $(CONN)

clean-all:  ## Full teardown including infra DB + PAT (prompts for confirmation)
	scripts/99_cleanup-infra.sh -c $(CONN)

# -- Code quality --------------------------------------------------------------

lint:  ## Run ruff check + format check
	uv run ruff check app/ tests/ && uv run ruff format --check app/ tests/

fmt:  ## Auto-format with ruff
	uv run ruff format app/ tests/ && uv run ruff check --fix app/ tests/

typecheck:  ## Type-check app/lib/ with ty
	uv run ty check app/lib/

arch:  ## Enforce layering: lib.ingest/config must not import streamlit (import-linter)
	# Run from app/ so `lib` resolves to app/lib; --project .. uses the root dev venv.
	cd app && uv run --project .. lint-imports

hooks:  ## Run all pre-commit hooks against every file
	uvx pre-commit run --all-files

# -- Help ----------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
