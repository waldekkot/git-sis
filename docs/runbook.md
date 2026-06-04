# Release & Rollback Runbook

Operational procedures for releasing and rolling back the Ingestion Ops Console
(`SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE`).

See `docs/WAYS-OF-WORKING.md` §5.1 for the rationale.

## Version model

| Channel | What it is | How it updates |
|---|---|---|
| **LIVE** | The mutable version every viewer sees | Each merge to `main` redeploys it (ci.yml `deploy-to-sis`, gated by `prod`) |
| **MAIN_\<sha\>** aliases | Every CI main-branch deploy commits a named snapshot | Created automatically by `deploy-to-sis` job after each push to `main` |
| **V1_2_3** aliases | Semver release snapshots | Created by pushing a `vX.Y.Z` git tag (release.yml) |
| **DEFAULT_VERSION** | The version pinned for viewers, if set | Set/reset manually for rollback |

`vX.Y.Z` tags are sanitized to valid Snowflake identifiers: `v1.2.3` → `V1_2_3`
(dots/dashes → `_`, uppercased) in `scripts/30_deploy.sh`.

`MAIN_<sha>` aliases use the first 7 characters of the commit SHA, uppercased.

## Cut a release

```bash
# 1. Merge to main (deploys LIVE via the gated prod environment).
# 2. Tag the commit you want to immortalize:
git tag v1.2.3
git push origin v1.2.3
# → release.yml deploys and runs:
#     ALTER STREAMLIT ... COMMIT VERSION V1_2_3;
# (awaits prod-environment approval before it runs)
```

Confirm:
```sql
SHOW VERSIONS IN STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE;
```

## Roll back to any main-branch deploy (seconds, no redeploy)

Every push to `main` that CI deploys creates a `MAIN_<sha>` version alias.
Pin viewers to any prior deploy by SHA:

```sql
-- 1. Find available versions:
SHOW VERSIONS IN STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE;

-- 2. Pin to a specific main-branch deploy:
ALTER STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE
  SET DEFAULT_VERSION = MAIN_A1B2C3D;   -- first 7 chars of the target commit SHA
```

Or roll back to a semver release:

```sql
ALTER STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE
  SET DEFAULT_VERSION = V1_2_2;   -- prior good semver alias from SHOW VERSIONS
```

To return to tracking LIVE after a fix ships:
```sql
ALTER STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE
  ADD LIVE VERSION FROM LAST;
```

Verify which version is serving:
```sql
DESCRIBE STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE;
-- inspect live_version_* / default_version_* columns
```

## Retention

Keep the last ~10 committed versions. Drop older ones:
```sql
-- list, then drop the oldest you no longer need:
ALTER STREAMLIT SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE DROP VERSION V0_9_0;
```

## Incident quick reference

| Situation | Action |
|---|---|
| Bad deploy on LIVE | `SET DEFAULT_VERSION = <prior alias>` (instant) |
| Need to inspect a past release | `SHOW VERSIONS IN STREAMLIT ...` |
| Deploy job failed mid-way | Re-run the `deploy-to-sis` job; LIVE is unchanged until deploy succeeds |
| Prod approval pending | Approve in GitHub → Actions run → Review deployments (prod) |

## Reference
- [BCR-1888 — ALTER STREAMLIT versioning](https://docs.snowflake.com/en/release-notes/bcr-bundles/2025_01/bcr-1888)
