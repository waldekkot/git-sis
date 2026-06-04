# Terraform for git-sis — Account-Level Objects

Manages Snowflake account-level objects that cannot be expressed in DCM
(tables/views/schemas → DCM; warehouses/databases/integrations → here).

## IaC boundary

| Layer | Tool | Files |
|---|---|---|
| Tables / views / schemas | **DCM** | `dcm/definitions/` |
| Database | **Terraform** | `terraform/database.tf` |
| Warehouse | **Terraform** | `terraform/warehouse.tf` |
| API integration (GitHub App) | **Terraform** | `terraform/api_integration.tf` |
| App code | **Git + snow CLI / pull-based** | `app/`, `.github/workflows/` |

## Prerequisites

1. [Terraform CLI ≥ 1.9](https://developer.hashicorp.com/terraform/install)
2. Snowflake credentials with SYSADMIN or equivalent role

## Quick start

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your account identifier and settings

terraform init
terraform plan   # preview changes
terraform apply  # create resources
```

## Authentication

Set environment variables before running Terraform:

```bash
# Key-pair (recommended for CI):
export SNOWFLAKE_ACCOUNT=sfseeurope-wkot_demo1
export SNOWFLAKE_USER=my_user
export SNOWFLAKE_PRIVATE_KEY_PATH=~/.snowflake/rsa_key.p8

# Or browser SSO (local dev):
export SNOWFLAKE_ACCOUNT=sfseeurope-wkot_demo1
export SNOWFLAKE_USER=my_user
export SNOWFLAKE_AUTHENTICATOR=EXTERNALBROWSER
```

## State management

**Do NOT commit `terraform.tfstate` or `terraform.tfstate.backup`** — they
may contain secrets. Configure a remote backend in `providers.tf`:

- **AWS S3**: uncomment the `backend "s3"` block
- **Terraform Cloud / HCP**: uncomment the `cloud` block
- **Local** (dev only): default; state stays on disk and is gitignored

## Importing existing resources

If these resources already exist in Snowflake, import them rather than
letting Terraform try to create them (which would fail with "already exists"):

```bash
terraform import snowflake_database.learning_db SNOWFLAKE_LEARNING_DB
terraform import snowflake_warehouse.app_warehouse COMPUTE_WH
terraform import snowflake_api_integration.github_app GIT_API_WALDEKKOT
```

## CI integration

For CI-managed Terraform, add a workflow that runs `terraform plan` on PRs
and `terraform apply` on merge to main. Use key-pair auth (no password) via
GitHub Actions secrets:

```yaml
- name: Terraform plan
  run: terraform -chdir=terraform plan
  env:
    SNOWFLAKE_ACCOUNT: ${{ vars.GIT_SIS_SF_ACCOUNT }}
    SNOWFLAKE_USER: ${{ secrets.TF_SNOWFLAKE_USER }}
    SNOWFLAKE_PRIVATE_KEY: ${{ secrets.TF_SNOWFLAKE_PRIVATE_KEY }}
```

## What's NOT here

- Schemas, tables, views → managed by DCM (`dcm/`)
- Snowflake roles and grants for CI SERVICE users → managed manually
  (see `docs/oidc-setup.md`); add to `terraform/iam.tf` when ready to codify
