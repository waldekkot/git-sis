# OIDC Setup — Secretless CI Authentication (Workload Identity Federation)

The pipeline authenticates to Snowflake with **short-lived GitHub OIDC tokens** via
Workload Identity Federation (WIF). No `SF_PAT_TOKEN`, private key, or password is stored
in GitHub.

This must be configured once on the Snowflake account **before** the workflows can reach
Snowflake (the migration to OIDC is a hard cutover — `SF_PAT_TOKEN` is no longer used).

## How the subject maps to a user

GitHub issues an OIDC token whose `sub` claim identifies the workflow. A job that sets
`environment: X` emits the subject `repo:<owner>/<repo>:environment:X` **regardless of
trigger**. We use one SERVICE user per environment:

| Workflow / job | `environment:` | OIDC subject | Snowflake user |
|---|---|---|---|
| `ci.yml` → integration-tests | `ci` | `repo:waldekkot/git-sis:environment:ci` | `CI_SVC_CI` |
| `preview.yml` → preview-deploy | `preview` | `repo:waldekkot/git-sis:environment:preview` | `CI_SVC_PREVIEW` |
| `ci.yml` → deploy-to-sis, `release.yml` | `prod` | `repo:waldekkot/git-sis:environment:prod` | `CI_SVC_PROD` |

> Replace `waldekkot/git-sis` with your `<owner>/<repo>` if forking.

## 1. Snowflake side (run once, ACCOUNTADMIN)

```sql
-- One SERVICE user per environment subject. TYPE = SERVICE users cannot log in
-- interactively and authenticate only via the federated OIDC token.

CREATE OR REPLACE USER CI_SVC_CI
  TYPE = SERVICE
  DEFAULT_ROLE = SYSADMIN
  WORKLOAD_IDENTITY = (
    TYPE = OIDC
    ISSUER = 'https://token.actions.githubusercontent.com'
    SUBJECT = 'repo:waldekkot/git-sis:environment:ci'
  );

CREATE OR REPLACE USER CI_SVC_PREVIEW
  TYPE = SERVICE
  DEFAULT_ROLE = SYSADMIN
  WORKLOAD_IDENTITY = (
    TYPE = OIDC
    ISSUER = 'https://token.actions.githubusercontent.com'
    SUBJECT = 'repo:waldekkot/git-sis:environment:preview'
  );

CREATE OR REPLACE USER CI_SVC_PROD
  TYPE = SERVICE
  DEFAULT_ROLE = SYSADMIN
  WORKLOAD_IDENTITY = (
    TYPE = OIDC
    ISSUER = 'https://token.actions.githubusercontent.com'
    SUBJECT = 'repo:waldekkot/git-sis:environment:prod'
  );

-- Grant each the role it needs. SYSADMIN here for the demo; in production grant a
-- least-privilege custom role (CREATE STREAMLIT / SCHEMA on the target DB only).
GRANT ROLE SYSADMIN TO USER CI_SVC_CI;
GRANT ROLE SYSADMIN TO USER CI_SVC_PREVIEW;
GRANT ROLE SYSADMIN TO USER CI_SVC_PROD;

-- Default warehouse (avoids "No active warehouse selected" errors)
ALTER USER CI_SVC_CI      SET DEFAULT_WAREHOUSE = COMPUTE_WH;
ALTER USER CI_SVC_PREVIEW SET DEFAULT_WAREHOUSE = COMPUTE_WH;
ALTER USER CI_SVC_PROD    SET DEFAULT_WAREHOUSE = COMPUTE_WH;
```

### Network policy for CI runners

If your account has a VPN-restricted network policy (common in SE/field accounts), GitHub
Actions runners will be blocked with `250001: IP not allowed to access Snowflake`. Fix this
with a **per-user** network policy that doesn't weaken the account-level policy:

```sql
-- Allow all IPs (GitHub Actions uses dynamic runner IPs)
CREATE OR REPLACE NETWORK POLICY CI_GITHUB_ACTIONS_POLICY
  ALLOWED_IP_LIST = ('0.0.0.0/0')
  COMMENT = 'Allows GitHub Actions runners (SERVICE users only)';

-- Assign ONLY to CI SERVICE users (not to interactive users)
ALTER USER CI_SVC_CI      SET NETWORK_POLICY = CI_GITHUB_ACTIONS_POLICY;
ALTER USER CI_SVC_PREVIEW SET NETWORK_POLICY = CI_GITHUB_ACTIONS_POLICY;
ALTER USER CI_SVC_PROD    SET NETWORK_POLICY = CI_GITHUB_ACTIONS_POLICY;
```

> **Security note:** The permissive IP range is acceptable here because:
> 1. SERVICE users authenticate exclusively via OIDC — no password/key to brute-force.
> 2. OIDC tokens are short-lived (~5 min) and scoped to a specific repo + environment.
> 3. The account-level VPN policy still protects all interactive (human) users.

## 2. GitHub side (repo Settings)

1. **Settings → Environments**: create `ci`, `preview`, `prod`.
   - `prod`: add **Required reviewers** (the approval gate). Optionally restrict to the
     `main` branch and `v*` tags.
   - `ci` and `preview`: **no** required reviewers (so they run unattended).
2. **Settings → Secrets and variables → Actions → Variables** (optional overrides):
   - `GIT_SIS_SF_ACCOUNT` (defaults to `sfseeurope-wkot_demo1`)
   - `GIT_SIS_SF_USER_CI`, `GIT_SIS_SF_USER_PREVIEW`, `GIT_SIS_SF_USER_PROD`
     (default to `CI_SVC_CI` / `CI_SVC_PREVIEW` / `CI_SVC_PROD`)
3. **Remove `SF_PAT_TOKEN`** from Settings → Secrets (no longer used).

## How the workflows wire it (already done)

Each Snowflake-touching job:
- declares `permissions: { id-token: write, contents: read }`,
- sets `environment:` to drive the subject and (for prod) the approval gate,
- runs `snowflakedb/snowflake-cli-action@v2` with `use-oidc: true` and
  `oidc-token-name: SNOWFLAKE_CONNECTIONS_<ENV>_TOKEN`,
- then the composite action `.github/actions/setup-snowflake` writes the OIDC token
  **inline** into `~/.snowflake/config.toml` (`token = "..."`) with `::add-mask::`.

### Why inline token (not env-var or token_file_path)?

| Approach | Works? | Notes |
|---|---|---|
| `SNOWFLAKE_CONNECTIONS_CI_TOKEN` env var | ❌ for Snowpark | `Session.builder.config("connection_name", ...)` doesn't read env-var overrides for `token`. |
| `token_file_path = "/tmp/..."` | ❌ | Wraps content in a PAT attestation envelope — wrong format for raw OIDC JWT. |
| `token = "<jwt>"` in config.toml | ✅ | Read directly by both `snow` CLI and Snowpark connector. |

The `::add-mask::` GitHub Actions command ensures the token value never appears in logs,
even in a public repo.

## Verifying

A quick connection check inside any OIDC job:
```bash
snow connection test -c ci
```

## Reference
- [Snowflake CLI GitHub Action — OIDC](https://docs.snowflake.com/en/developer-guide/snowflake-cli/cicd/github-action)
- [Snowflake Workload Identity Federation](https://docs.snowflake.com/en/user-guide/workload-identity-federation)
- [GitHub OIDC subject claims](https://docs.github.com/en/actions/reference/security/oidc)
