# Ways of Working — Streamlit + SiS + Snowpark repos

A team enablement blueprint, derived from the `git-sis` reference repo. It describes
*how to work* with this class of project — Streamlit-in-Snowflake (SiS) apps backed by
Snowpark logic, developed in Workspaces or locally, and shipped through GitHub Actions.

The focus is **process**, not code: rapid iteration, modularity, testability, ease of
amendment, and developer speed across both the **inner loop** (laptop/emulator) and the
**outer loop** (git + Snowflake).

> Use this as the checklist when starting a new SiS/Snowpark repo, and as the rubric when
> reviewing an existing one.

---

## 0. Scorecard (this repo, as a baseline)

| Area | Maturity | Notes |
|---|---|---|
| Inner loop (Dev) | ★★★★☆ | Local-testing emulator + AppTest + session seam + watch mode. Gap: reproducible env, connection ergonomics. |
| Modularity / testability | ★★★★★ | `lib/` (logic, Streamlit-free) vs `pages/` (UI) vs `session.py` (one seam). Enforced by `import-linter`. |
| CI gating | ★★★★★ | 3-stage gate (unit → integration → deploy). OIDC auth. Prod approval gate. import-linter in CI. |
| GitOps / previews | ★★★★★ | Per-PR isolated schema + auto URL comment + teardown (OIDC, env:preview). |
| Release mgmt / rollback | ★★★★★ | Semver tags → `release.yml` → `COMMIT VERSION` → instant rollback via `SET DEFAULT_VERSION`. |
| Env promotion (dev→prod) | ★★★★★ | GitHub Environments (ci/preview/prod) with required reviewer gate on prod. |
| Secrets posture | ★★★★★ | **Zero stored secrets.** Git = OAuth2 (GitHub App). CI = OIDC (Workload Identity Federation). No PATs anywhere. |

---

## 1. Reference architecture — the five non-negotiables

Copy these into every SiS/Snowpark repo. They are the load-bearing decisions.

### 1.1 The session seam — the only environment branch allowed
`app/lib/session.py` is the single place that differs between laptop and SiS:

```python
try:
    return get_active_session()                       # SiS: embedded identity, no secrets
except Exception:
    conn = os.getenv("SNOWFLAKE_DEFAULT_CONNECTION_NAME") or "default"
    return Session.builder.config("connection_name", conn).create()  # local
```

Everything above it (ingestion logic, UI) is identical in both environments. **Team rule:
no other file may branch on environment.** "Write once, run in two places."

### 1.2 Layering that makes logic testable

Four-layer model, from innermost (data) to outermost (UI):

```
lib/config.py          table FQNs (env-var overridable, Streamlit-free)
     ↓ imported by
lib/ingest.py          Snowpark DataFrame logic (Streamlit-free, emulator-testable)
     ↓ data passed as args to
lib/components/        shared UI components (CAN import streamlit, no lib.ingest/config import)
     ↓ called from
lib/session.py         session seam (only file with @st.cache_resource)
pages/, streamlit_app.py  thin UI orchestration
```

Contracts (enforced by `import-linter`, `make arch`, and pre-commit):
- `lib.ingest` + `lib.config` → **forbidden**: `streamlit`
- `lib.components` → **forbidden**: `lib.ingest`, `lib.config`
  (data flows in through function arguments, not module imports)

Result: logic is unit-testable with zero Streamlit runtime. Enforce this boundary
mechanically (see `app/.importlinter`), not by discipline.

### 1.3 Snowpark local-testing emulator drives the inner loop
Unit tests run in-process (`Session.builder.config("local_testing", True)`), **no
credentials, ~2s**. This is what makes TDD viable for Snowpark. Discipline:
> Mock only what the emulator cannot provide; inject everything that is configurable.

### 1.4 `AppTest` for credential-free UI + data assertions
`AppTest.from_file(...)` driven against the emulator session gives end-to-end UI tests
that also assert on real rows written by Snowpark. No `MagicMock` in the happy path.

### 1.5 One parameterised deploy artifact
`app/snowflake.yml` uses `ctx.env` defaults so the *same* file deploys to dev, per-PR
preview, and prod by swapping env vars — no config-by-branch drift.

```yaml
identifier:
  name:     <% ctx.env.GIT_SIS_APP_NAME | default('INGEST_CONSOLE') %>
  schema:   <% ctx.env.GIT_SIS_SCHEMA   | default('GIT_SIS') %>
  database: <% ctx.env.GIT_SIS_DATABASE | default('SNOWFLAKE_LEARNING_DB') %>
```

---

## 2. The two-loop model (how to teach it)

```
INNER LOOP (seconds)                 OUTER LOOP (minutes)
edit → ptw (watch) ─┐                push → PR → preview app ─┐
streamlit run ──────┼─ green ──►     CI: unit→integ→deploy ───┼─► versioned release
make test ──────────┘                merge → main deploy ─────┘     → rollback ready
```

- **Inner = laptop, emulator, no Snowflake account.** Optimise for *latency to red/green*.
- **Outer = git forge + Snowflake.** Optimise for *isolation, safety, reversibility*.

---

## 3. Deploy mechanisms — the three ways, and when to use each

| | A. snow CLI push *(current)* | B. GIT REPOSITORY pull | C. Workspaces (Snowsight) |
|---|---|---|---|
| Who moves code | CI / laptop pushes to stage | Snowflake `FETCH`es from GitHub | Snowsight git-backed, manual Deploy |
| Source of truth | Git → CI → stage | Git (Snowflake mirrors a branch) | Git (commit/push from Snowsight) |
| Best for | Deploys that **also create tables / integrations / RBAC** (this repo) | **Trunk-based** + per-branch live previews, minimal setup | **Interactive iteration**, non-CLI users, pairing |
| CI→Snowflake credential | CI holds it (PAT today → OIDC) | n/a for refresh; FETCH runs in Snowflake | User's Snowsight session |
| Git credential | n/a | **GitHub App OAuth2** (no PAT) | **GitHub App OAuth2** (no PAT) |
| Quality gates | Strong (full CI before deploy) | Weak unless paired with CI `snow git fetch` | Weak (manual) |
| Reproducibility | High | High | Lower (env-dependent) |
| Refresh trigger | n/a (CI uploads) | `ALTER GIT REPOSITORY FETCH` (task or CI; **no webhook**) | Pull button |
| Rollback | Re-deploy prior commit / version alias | Repoint branch/commit URI | Re-pull prior commit |

**Decision rule for the team:**
1. **Develop** in **C (Workspaces)** *or* locally (`make dev`) — both are first-class.
2. **Promote with A (push)** because this app provisions non-Streamlit objects (schema,
   tables, EAI). Push-based CI is the only mechanism that co-deploys the Streamlit object
   **and** its dependencies behind one gate.
3. **Use B (pull) for ephemeral branch previews** if you want zero-CI previews —
   `CREATE STREAMLIT FROM @repo/branches/<feature>` gives a live app per branch.
4. **Layer versioning (§5.1) on top regardless of A/B/C** — that is what gives rollback.

This repo supports all three (`make deploy`, `make deploy-git`/`deploy-sql`, and the
Workspace flow). Keeping tri-modal support is itself a blueprint feature.

---

## 4. Inner-loop improvements (developer velocity)

### 4.1 Reproducible environment — `.devcontainer` / `mise`
Onboarding assumes local `uv` + Python 3.11. Add a `.devcontainer.json` (or `mise.toml`)
pinning both, so `make init` is truly one-command on any machine. *Impact: high · Effort: low.*

### 4.2 Connection ergonomics — `.envrc` (direnv)
Devs currently `export SNOWFLAKE_DEFAULT_CONNECTION_NAME` by hand (a known "wrong account"
footgun). A committed `.envrc.example` auto-loads the connection per directory:

```bash
# .envrc.example  (copy to .envrc; direnv allow)
export SNOWFLAKE_DEFAULT_CONNECTION_NAME=oregon-sedemo
```
*Impact: med · Effort: low.*

### 4.3 Make the watch loop the advertised ritual
`make test-watch` exists but isn't the headline command. Promote `ptw` as *the* inner-loop
entry point in README and tutorial; keep `--no-cov` on watch for sub-second feedback.
*Impact: med · Effort: trivial.*

### 4.4 Treat the "emulator gaps" as a living doc + PR gate
The emulator's gaps (`uniform`, `round`, `UUID_STRING`, no `session.sql()`) are the #1
source of "works locally, breaks live." Keep a single `docs/emulator-gaps.md` mapping
*gap → patch → why*, and make `make test-live` (cross-validate units against real
Snowflake) part of the PR checklist. *Impact: high · Effort: low.*

### 4.5 Enforce the layering boundary with a linter
Add `import-linter` so `app.lib` importing `streamlit` becomes a CI failure, not a code-
review nicety. Protects testability as the team grows.

```ini
# .importlinter (recommended)
[importlinter]
root_package = lib

[importlinter:contract:logic-has-no-ui]
name = lib must not import streamlit
type = forbidden
source_modules = lib.ingest
                 lib.config
forbidden_modules = streamlit
```
*Impact: high (long-term) · Effort: low.*

### 4.6 Deterministic local seed data
`make dev` hits a real connection and shows whatever is in the schema. Add `make seed` to
load a fixed fixture so every dev's local app looks identical. *Impact: med · Effort: med.*

---

## 5. Outer-loop improvements (DevOps / GitOps)

### 5.1 Versioned releases + rollback runbook — ✅ IMPLEMENTED
SiS supports `ALTER STREAMLIT … ADD VERSION / COMMIT / SET DEFAULT_VERSION / ABORT`.

- On `v*.*.*` tag push: `release.yml` deploys → `COMMIT VERSION V<sanitized_tag>`.
- **Rollback = `ALTER STREAMLIT … SET DEFAULT_VERSION = <prior>`** (seconds, no redeploy).
- Full procedure documented in `docs/runbook.md`.
- Tag naming: `v1.2.3` → `V1_2_3` (dots/dashes become underscores for Snowflake identifiers).

### 5.2 GitHub Environments + prod approval gate — ✅ IMPLEMENTED
Three environments: `ci` (auto, integration tests), `preview` (auto, PR ephemeral), `prod`
(required reviewer gate). OIDC subject is scoped per-environment. Prod deploy pauses until
a maintainer approves.

### 5.3 Secrets posture — ✅ FULLY SECRETLESS
- **Git auth (Snowflake → GitHub):** GitHub App OAuth2 — no PAT, no rotation.
- **CI auth (GitHub Actions → Snowflake):** OIDC via Workload Identity Federation.
  `snowflakedb/snowflake-cli-action@v2` with `use-oidc: true`. SERVICE users per environment
  (`CI_SVC_CI`, `CI_SVC_PREVIEW`, `CI_SVC_PROD`) with OIDC subjects. `SF_PAT_TOKEN` removed.
- **Network policy:** Per-user `CI_GITHUB_ACTIONS_POLICY` (0.0.0.0/0) assigned only to SERVICE
  users — doesn't weaken the account VPN policy for interactive users.
- **Key learnings:**
  - Snowpark `Session.builder` doesn't read `SNOWFLAKE_CONNECTIONS_*_TOKEN` env vars — must
    write `token = "..."` inline in config.toml (masked with `::add-mask::`).
  - `token_file_path` wraps content in an attestation envelope (wrong for raw OIDC JWT).
  - `default-config-file-path: __skip__` avoids `cp` errors in the CLI action.

### 5.4 Supply-chain hardening on the pipeline
- Pin GitHub Actions to **commit SHAs**, not mutable `@v4` tags.
- Add **Dependabot/Renovate** for `uv.lock` and the Actions.
- Add concurrency control so rapid pushes don't stack duplicate preview deploys:

```yaml
# in preview.yml (recommended)
concurrency:
  group: preview-${{ github.event.number }}
  cancel-in-progress: true
```
*Impact: med · Effort: low.*

### 5.5 Post-deploy smoke gate in CI
`EXECUTE STREAMLIT` is unsupported on the container runtime, but `scripts/40_verify.sh`
(DESCRIBE + URL) is **not currently a step in the deploy job**. Add it so a broken deploy
fails the pipeline instead of shipping silently. Optionally add a Snowpark liveness query
(`SELECT 1` + table existence). *Impact: med · Effort: low.*

### 5.6 Graduate DDL to managed migrations
`deploy/*.sql` is hand-ordered idempotent SQL (the repo already notes a "DCM graduation").
As schema evolves, move to **`snow dcm`** (Database Change Management) or schemachange for
ordered, versioned, auditable migrations — so schema changes get the same review/rollback
story as app code. *Impact: med (scales with project) · Effort: med.*

### 5.7 Branch protection + required checks
Make `unit-tests` a required status check on `main`; require PR review. Cheap governance
the preview workflow already makes painless. *Impact: med · Effort: trivial.*

---

## 6. Prioritized punch list (impact × effort)

> **Implementation status (this repo):** items 1–5 are now implemented, plus the
> post-deploy smoke gate (§5.5). See `docs/runbook.md`, `docs/oidc-setup.md`,
> `docs/emulator-gaps.md`, `app/.importlinter`, `.github/workflows/release.yml`, and the
> OIDC/environment wiring in `ci.yml` + `preview.yml`. Remaining: 6, 7, 10, 11.

| # | Improvement | Loop | Impact | Effort | Status |
|---|---|---|---|---|---|
| 1 | Versioned releases + rollback runbook (§5.1) | Outer | ★★★ | ●● | ✅ done |
| 2 | CI→Snowflake OIDC, remove `SF_PAT_TOKEN` (§5.3) | Outer | ★★★ | ● | ✅ done |
| 3 | GitHub Environments + prod approval (§5.2) | Outer | ★★★ | ● | ✅ wired (set reviewers in Settings) |
| 4 | Enforce `lib` ≠ `streamlit` via import-linter (§4.5) | Inner | ★★★ | ● | ✅ done |
| 5 | Living "emulator gaps" doc + `test-live` in PR checklist (§4.4) | Inner | ★★★ | ● | ✅ done |
| 5b | Post-deploy smoke gate (§5.5) | Outer | ★★ | ● | ✅ done |
| 6 | `.devcontainer`/`mise` one-command env (§4.1) | Inner | ★★ | ● | todo |
| 7 | Pin Actions to SHA + Dependabot + concurrency (§5.4) | Outer | ★★ | ● | todo |
| 9 | direnv `.envrc.example` (§4.2) | Inner | ★★ | ● | todo |
| 10 | `make seed` deterministic fixtures (§4.6) | Inner | ★★ | ●● | todo |
| 11 | DCM/schemachange migrations (§5.6) | Outer | ★★ | ●● | todo |
| 12 | Branch protection / required checks (§5.7) | Outer | ★★ | ● | partial (required check set in Settings) |

> ✅ The pipeline is now **fully secretless**: Git auth = OAuth2, CI auth = OIDC.
> No PATs, no rotation, no stored secrets. See `docs/oidc-setup.md` for the full setup.

---

## 7. Anti-patterns this repo correctly avoids (teach these)

- ❌ `session.sql()` strings in app logic → ✅ DataFrame API (keeps logic emulator-testable).
- ❌ Environment branching scattered across files → ✅ one session seam.
- ❌ `streamlit` imports in business logic → ✅ thin UI, fat `lib`.
- ❌ Config-by-branch drift → ✅ one `snowflake.yml` + `ctx.env`.
- ❌ Shared mutable dev schema → ✅ per-PR `GIT_SIS_PR_<n>` + auto-teardown.
- ❌ Mock-everything tests → ✅ inject the session, mock only emulator gaps.
- ❌ Shared/rotating git PATs → ✅ per-user GitHub App OAuth2.

---

## 8. New-repo adoption checklist

Inner loop:
- [ ] `app/lib/session.py` seam (the only env branch)
- [ ] `lib/` Streamlit-free; UI in `pages/` + entry file
- [ ] Snowpark local-testing emulator unit tests (no creds)
- [ ] `AppTest` UI tests against the emulator
- [ ] `uv` + `ruff` + `ty` + `pre-commit` + watch mode
- [ ] `.devcontainer`/`mise` + `.envrc.example`
- [ ] import-linter contract + `docs/emulator-gaps.md`

Outer loop:
- [ ] One `snowflake.yml` parameterised with `ctx.env`
- [ ] 3-stage CI: unit → integration (temp schema) → deploy
- [ ] Per-PR preview schema + URL comment + teardown
- [ ] Git auth via **GitHub App OAuth2**
- [ ] CI→Snowflake via **OIDC** (no PAT)
- [ ] GitHub Environments with prod approval
- [ ] Versioned releases + rollback runbook
- [ ] Post-deploy smoke gate
- [ ] Branch protection + required checks
- [ ] Actions pinned to SHA + Dependabot

---

## References
- [Streamlit in Snowflake in Workspaces](https://docs.snowflake.com/en/developer-guide/streamlit/streamlit-in-workspaces/streamlit-in-workspaces-overview)
- [Sync SiS apps with a Git repository](https://docs.snowflake.com/en/developer-guide/streamlit/features/git-integration)
- [BCR-1888: Git integration + versioning for SiS](https://docs.snowflake.com/en/release-notes/bcr-bundles/2025_01/bcr-1888)
- [Create your Streamlit app (CLI + GitHub Actions CI/CD)](https://docs.snowflake.com/en/developer-guide/streamlit/app-development/creating-your-app)
- [SiS deployment techniques — push vs pull](https://medium.com/snowflake/streamlit-in-snowflake-deployment-techniques-fc31f32fb391)
- [Using a Git repository in Snowflake](https://docs.snowflake.com/en/developer-guide/git/git-overview)
- Connect Snowflake to a Git provider with OAuth2 (GitHub App / GitLab OAuth2)
