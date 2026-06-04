# DCM Project Setup

One-time setup required before `make dcm-plan` / `make dcm-deploy` can run.

## Prerequisites

- Snowflake account with DCM Projects enabled (generally available)
- `SYSADMIN` role (or a role with `CREATE DCM PROJECT` privilege on the schema)
- CI SERVICE users need `EXECUTE DCM PROJECT` privilege

## Step 1: Create the DCM project objects

Run as SYSADMIN (or a role with CREATE privileges on the schema):

```sql
USE ROLE SYSADMIN;
USE DATABASE SNOWFLAKE_LEARNING_DB;
USE SCHEMA GIT_SIS;

-- Dev environment DCM project
CREATE DCM PROJECT IF NOT EXISTS SNOWFLAKE_LEARNING_DB.GIT_SIS.GIT_SIS_DCM
  SOURCE_LOCATION = 'dcm/'
  COMMENT = 'Declarative schema management for git-sis dev environment';

-- If you have a separate prod schema, create a project object there too:
-- CREATE DCM PROJECT IF NOT EXISTS PROD_DB.PROD_SCHEMA.GIT_SIS_DCM
--   SOURCE_LOCATION = 'dcm/'
--   COMMENT = 'Declarative schema management for git-sis prod environment';
```

## Step 2: Grant CI SERVICE users permission to execute DCM

```sql
-- Grant the CI and PROD service users permission to plan/deploy
GRANT EXECUTE DCM PROJECT
  ON DCM PROJECT SNOWFLAKE_LEARNING_DB.GIT_SIS.GIT_SIS_DCM
  TO ROLE <CI_SVC_CI role>;

GRANT EXECUTE DCM PROJECT
  ON DCM PROJECT SNOWFLAKE_LEARNING_DB.GIT_SIS.GIT_SIS_DCM
  TO ROLE <CI_SVC_PROD role>;
```

## Step 3: Verify

```bash
# From a local connection:
make dcm-plan    # should show "No changes" if schema is already up to date

# Or with snow CLI directly:
snow dcm plan \
  --project-name SNOWFLAKE_LEARNING_DB.GIT_SIS.GIT_SIS_DCM \
  --source dcm/ \
  -c default
```

## Workflow after setup

| Command | What it does |
|---|---|
| `make dcm-plan` | Preview what DCM would change (safe, read-only) |
| `make dcm-deploy` | Apply the changes to the target schema |
| `make dcm-plan CONN=prod` | Plan against prod schema |
| `make dcm-deploy CONN=prod` | Deploy to prod schema |

## CI integration

`ci.yml` runs `snow dcm plan` after integration tests and before the
deploy step. A plan that shows **destructive changes** (DROP TABLE, DROP COLUMN)
**fails the pipeline** — this is intentional. Destructive DDL changes require
explicit sign-off. To proceed:
1. Review the plan output
2. If intended: re-run CI with `[dcm-force]` in the commit message (handled in ci.yml)
3. If not intended: fix the definition in `dcm/definitions/` and push again

## Relationship to deploy/00_setup_env.sql

`deploy/00_setup_env.sql` remains as a **non-DCM fallback** for:
- Fresh environments without a DCM project object in place (e.g. first `make setup`)
- Environments where the DCM project hasn't been created yet

Once the DCM project object exists in an environment, DCM is the authoritative
source and `00_setup_env.sql` should not be run manually.
