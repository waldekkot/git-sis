<!-- Pull request template for git-sis. See docs/WAYS-OF-WORKING.md. -->

## What & why

<!-- 1-3 sentences: what this changes and the reason. -->

## How to verify

<!-- Commands a reviewer can run, or the PR preview app URL (auto-posted below). -->

## Checklist

Inner loop (laptop, no credentials):
- [ ] `make test` green (unit + AppTest against the Snowpark emulator)
- [ ] `make lint` and `make typecheck` clean
- [ ] `make arch` passes (no `streamlit` import leaked into `lib.ingest` / `lib.config`)
- [ ] New emulator patches (if any) documented in `docs/emulator-gaps.md`

Cross-validation against real Snowflake (when logic touches Snowpark/SQL):
- [ ] `make test-live` run locally (same unit tests, real engine) — **required if you
      added/changed an emulator patch or any `lib/ingest.py` logic**
- [ ] `make test-integration` run locally (or rely on the CI `integration-tests` job)

Outer loop:
- [ ] PR preview app deployed and sanity-checked (URL in the auto-comment below)
- [ ] If this is a release-worthy change: a `vX.Y.Z` tag will be pushed after merge
      (triggers the versioned prod deploy — see `docs/runbook.md`)
