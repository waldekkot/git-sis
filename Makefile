# Makefile — common developer commands for git-sis
# Usage: make <target>   e.g. make test  or  make dev
#
# All Snowflake targets default to the 'oregon-sedemo' connection.
# Override: make deploy CONN=my-other-conn
#
CONN ?= oregon-sedemo
SNOWFLAKE_DEFAULT_CONNECTION_NAME ?= $(CONN)
export SNOWFLAKE_DEFAULT_CONNECTION_NAME

.PHONY: install test test-watch test-full test-integration test-live \
        dev deploy verify clean lint help

# -- Dependencies --------------------------------------------------------------

install:  ## Install deps + pre-commit hooks (one-time setup)
	uv sync && uv run pre-commit install

# -- Testing -------------------------------------------------------------------

test:  ## Fast unit tests (Snowpark local emulator + AppTest, ~2s) — TDD inner loop
	uv run pytest tests/unit/ -v --tb=short

test-watch:  ## Watch unit tests on file change (requires pytest-watch: uv add --dev pytest-watch)
	uv run ptw tests/unit/ -- -x --tb=short

test-full:  ## Unit + integration tests against real Snowflake (~60s, needs credentials)
	uv run pytest tests/ -v --tb=short

test-integration:  ## Integration tests only (real Snowflake, temp schema, ~60s)
	uv run pytest tests/integration/ -v --tb=short

test-live:  ## Cross-validate unit tests against real Snowflake (use before merging)
	uv run pytest tests/unit/ -v --snowflake-session=live

# -- Local development ---------------------------------------------------------

dev:  ## Start the app locally against real Snowflake (port 8501)
	scripts/20_run-local.sh -c $(CONN)

dev-port:  ## Start locally on a custom port: make dev-port PORT=8533
	scripts/20_run-local.sh -c $(CONN) -p $(PORT)

# -- Snowflake setup (one-time) ------------------------------------------------

setup:  ## Create infra DB + GIT_SIS schema + tables
	scripts/10_setup.sh -c $(CONN)

setup-git:  ## Setup + optional git wiring for Snowsight workspace git-sync
	scripts/10_setup.sh -c $(CONN) --with-git

# -- Deploy --------------------------------------------------------------------

deploy:  ## Deploy to SiS via snow streamlit deploy (workspace-native)
	scripts/30_deploy.sh -c $(CONN)

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

hooks:  ## Run all pre-commit hooks against every file
	uvx pre-commit run --all-files

# -- Help ----------------------------------------------------------------------

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
