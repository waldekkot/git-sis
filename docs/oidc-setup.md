# OIDC Setup — Secretless CI Authentication

Replaces `SF_PAT_TOKEN` in GitHub Secrets with short-lived OpenID Connect tokens.
No long-lived credentials stored anywhere.

## Snowflake side (run once, ACCOUNTADMIN)

```sql
-- 1. Create the OIDC security integration
CREATE OR REPLACE SECURITY INTEGRATION github_oidc
    TYPE = EXTERNAL_OAUTH
    EXTERNAL_OAUTH_TYPE = CUSTOM
    EXTERNAL_OAUTH_ISSUER = 'https://token.actions.githubusercontent.com'
    EXTERNAL_OAUTH_JWS_KEYS_URL = 'https://token.actions.githubusercontent.com/.well-known/jwks'
    EXTERNAL_OAUTH_AUDIENCE_LIST = ('snowflakecomputing.com')
    -- Restrict to pushes on main from your repo:
    EXTERNAL_OAUTH_TOKEN_USER_MAPPING_CLAIM = 'sub'
    EXTERNAL_OAUTH_SNOWFLAKE_USER_MAPPING_ATTRIBUTE = 'login_name'
    ENABLED = TRUE;

-- 2. Create a dedicated service user for CI (do NOT use your personal user)
CREATE USER IF NOT EXISTS ci_service_user
    LOGIN_NAME = 'repo:waldekkot/git-sis:ref:refs/heads/main'
    -- For PR jobs:
    -- LOGIN_NAME = 'repo:waldekkot/git-sis:pull_request'
    TYPE = SERVICE;

-- 3. Grant the CI user the roles it needs
GRANT ROLE SYSADMIN TO USER ci_service_user;
```

## GitHub Actions side

Replace the composite action in each job with:

```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: snowflakedb/snowflake-cli-action@v2
    with:
      use-oidc: true
      cli-version: "3.19"
  - name: Deploy
    env:
      SNOWFLAKE_ACCOUNT: ${{ secrets.SNOWFLAKE_ACCOUNT }}
      SNOWFLAKE_USER: ci_service_user
    run: scripts/30_deploy.sh
```

Then remove `SF_PAT_TOKEN` from GitHub Secrets (Settings → Secrets → Actions).

## Reference

- [Snowflake Workload Identity Federation](https://docs.snowflake.com/en/user-guide/admin-security-fed-auth-use)
- [snowflakedb/snowflake-cli-action OIDC docs](https://docs.snowflake.com/en/developer-guide/snowflake-cli/cicd/github-action)
