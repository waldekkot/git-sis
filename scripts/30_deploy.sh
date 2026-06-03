#!/usr/bin/env bash
# 30_deploy.sh -- deploy the Ingestion Ops Console to Snowflake SiS.
#
# Uses snow streamlit deploy (workspace-native) with app/snowflake.yml for
# target DB/schema, compute pool, runtime, and EAI settings.
# This is both the CI/CD path (GitHub Actions) and the interactive CLI path
# (alternative to the Snowsight workspace Deploy button).
#
# Usage:
#   scripts/30_deploy.sh
#   scripts/30_deploy.sh -c my-conn
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#   -h, --help              Show this help text
#       --version           Print version and exit
#
# Workspace alternative:
#   Open app/ in Snowsight workspace → Run (private preview) → Deploy button
#   (uses the same app/snowflake.yml settings)

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

show_help() {
    cat <<EOF
git-sis $VERSION -- 30_deploy

Deploys SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE using
'snow streamlit deploy' (workspace-native approach).

Reads settings from app/snowflake.yml:
  compute_pool  SYSTEM_COMPUTE_POOL_CPU
  runtime       SYSTEM\$ST_CONTAINER_RUNTIME_PY3_11
  warehouse     COMPUTE_WH
  EAI           PYPI_ACCESS_INTEGRATION

On first run, snow CLI auto-creates the STREAMLIT_STAGE in GIT_SIS.
Subsequent runs replace the existing app (--replace).

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
    -h, --help              Show this help text
        --version           Print version and exit

EXAMPLES
    # Normal deploy after code change
    git push && scripts/30_deploy.sh

    # Deploy with a specific connection
    scripts/30_deploy.sh -c my-prod-conn

WORKSPACE ALTERNATIVE
    1. Open app/ in Snowsight workspace
    2. Press Run for a private development preview
    3. Press Deploy to publish (uses app/snowflake.yml)

NEXT STEP
    scripts/40_verify.sh   -- confirm app is live and get the URL
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
[[ $# -eq 0 ]] || die "Unknown argument: $1. Run with --help for usage."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$ROOT_DIR/app"

info "Deploying via snow streamlit deploy (connection: $CONN) ..."
info "Config: $APP_DIR/snowflake.yml"

snow streamlit deploy \
    -c "$CONN" \
    -p "$APP_DIR" \
    --replace

success "Deployed: SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE"
info "Run 'scripts/40_verify.sh' to confirm and get the URL."
