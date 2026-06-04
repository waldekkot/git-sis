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
```

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
  `oidc-token-name: SNOWFLAKE_CONNECTIONS_CI_TOKEN`,
- then the composite action `.github/actions/setup-snowflake` writes a token-free
  `config.toml` `[connections.ci]` block (account + service user +
  `authenticator = WORKLOAD_IDENTITY`).

The action exports `SNOWFLAKE_CONNECTIONS_CI_TOKEN` (the short-lived token) plus the
global `SNOWFLAKE_AUTHENTICATOR` / `SNOWFLAKE_WORKLOAD_IDENTITY_PROVIDER` /
`SNOWFLAKE_AUDIENCE` variables, so `snow ... -c ci` and the Snowpark integration tests
(`SNOWFLAKE_DEFAULT_CONNECTION_NAME=ci`) both authenticate without a stored secret.

## Verifying

A quick connection check inside any OIDC job:
```bash
snow connection test -c ci
```

## Reference
- [Snowflake CLI GitHub Action — OIDC](https://docs.snowflake.com/en/developer-guide/snowflake-cli/cicd/github-action)
- [Snowflake Workload Identity Federation](https://docs.snowflake.com/en/user-guide/workload-identity-federation)
- [GitHub OIDC subject claims](https://docs.github.com/en/actions/reference/security/oidc)
