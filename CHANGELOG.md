# Changelog

All notable changes to this project are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- Concurrency groups on all GitHub Actions workflows (prevent deploy races)
- `.envrc.example` for direnv-based connection switching
- Dependabot configuration for weekly GitHub Actions + uv dependency updates
- SHA-pinned GitHub Actions (supply chain hardening)
- Reusable unit-test workflow (`.github/workflows/reusable-unit-tests.yml`)
- Python 3.12 added to test matrix (forwards-compat signal)
- Smoke test tier as pytest (`tests/smoke/`) with `make test-smoke`
- Seed fixtures: `deploy/seed_data.sql` + `make seed` + `seeded_schema` integration fixture
- Emulator fidelity tests (`tests/unit/test_emulator_fidelity.py`) — living doc for Snowpark emulator gaps
- `lib/components/` layer slot with importlinter contract
- `scripts/check-docs.sh` — CI lint for tutorial drift
- `.devcontainer/devcontainer.json` — zero-setup onboarding via Codespaces or Docker
- `config/environments.yml` — single authoritative reference for environment identifiers
- `.github/workflows/deploy-gitops.yml` — pull-based GitOps deploy workflow
- Per-main-branch version alias committed after every deploy (rollback to any SHA)
- DCM project scaffold (`dcm/`) for declarative schema DDL management
- Terraform scaffold (`terraform/`) for account-level objects (warehouses, roles, API integrations)

### Changed
- Pages wrapped in `render()` functions for testability and argument injection
- `make init` now calls `make install` to avoid repeating Python setup steps
- Runtime dependencies in `app/pyproject.toml` pinned to prevent silent SiS upgrades

---

## [0.1.0] - 2026-06-04

### Added
- Initial release: Git-connected Streamlit-in-Snowflake ingestion ops console
- Three deploy mechanisms: push-based (`snow streamlit deploy`), pull-based (git fetch), Workspaces
- Snowpark local-testing emulator unit tests (zero credentials, ~2s)
- AppTest-based UI tests (`tests/unit/test_app.py`)
- Integration tests with isolated per-test schemas and xdist parallelism
- OIDC / Workload Identity Federation auth (zero stored secrets)
- Per-PR preview environments with bot comment and auto-cleanup
- Release versioning via `ALTER STREAMLIT COMMIT VERSION` + `SET DEFAULT_VERSION`
- GitHub Environments: `ci`, `preview`, `prod` with required-reviewer gate on prod
- `import-linter` architectural contract: `lib.ingest`/`lib.config` must never import `streamlit`
- `lib/` layering: `config` → `ingest` → `session` seam
- `docs/WAYS-OF-WORKING.md` — team enablement blueprint
- `docs/emulator-gaps.md` — known Snowpark local-testing limitations and workarounds
- `docs/oidc-setup.md` — one-time OIDC SERVICE user setup guide
- `docs/runbook.md` — rollback and operational procedures
- Tutorial HTML pages (6 chapters)

[Unreleased]: https://github.com/waldekkot/git-sis/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/waldekkot/git-sis/releases/tag/v0.1.0
