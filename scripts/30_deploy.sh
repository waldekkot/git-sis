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
#   scripts/30_deploy.sh --commit v1        # deploy + tag a stable version alias
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'default')
#       --commit ALIAS      After deploying, commit the live version as ALIAS.
#                           Uses ALTER STREAMLIT ... COMMIT (BCR-1888, 2025_01 bundle).
#                           Safe to skip on older accounts — prints a warning instead.
#   -h, --help              Show this help text
#       --version           Print version and exit
#
# Multi-env (env-var overrides for app/snowflake.yml):
#   GIT_SIS_DATABASE   target database  (default: SNOWFLAKE_LEARNING_DB)
#   GIT_SIS_SCHEMA     target schema    (default: GIT_SIS)
#   GIT_SIS_APP_NAME   app object name  (default: INGEST_CONSOLE)
#   GIT_SIS_WAREHOUSE  query warehouse  (default: COMPUTE_WH)
#
# Workspace alternative:
#   Open app/ in Snowsight workspace → Run (private preview) → Deploy button
#   (uses the same app/snowflake.yml settings)

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

COMMIT_ALIAS=""

show_help() {
    cat <<EOF
git-sis $VERSION -- 30_deploy

Deploys via 'snow streamlit deploy' (workspace-native approach).
Reads target DB/schema/app-name from app/snowflake.yml with env-var overrides.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --commit ALIAS      Tag live version as ALIAS after deploy
                            (requires BCR-1888 / 2025_01 bundle)
    -h, --help              Show this help text
        --version           Print version and exit

MULTI-ENV
    GIT_SIS_DATABASE=MY_DB GIT_SIS_SCHEMA=MY_SCHEMA \\
        scripts/30_deploy.sh -c prod-conn

    Or via Makefile:
        make deploy GIT_SIS_DATABASE=PROD_DB CONN=prod-conn

EXAMPLES
    # Normal deploy
    scripts/30_deploy.sh

    # Deploy + commit a named stable version
    scripts/30_deploy.sh --commit v1

    # Deploy to a PR preview schema
    GIT_SIS_SCHEMA=GIT_SIS_PR_42 GIT_SIS_APP_NAME=INGEST_CONSOLE_PR_42 \\
        scripts/30_deploy.sh -c ci

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
while [[ $# -gt 0 ]]; do
    case "$1" in
        --commit) shift; COMMIT_ALIAS="$1" ;;
        *) die "Unknown argument: $1. Run with --help for usage." ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
APP_DIR="$ROOT_DIR/app"

# Derive the fully-qualified app name from snowflake.yml env-var defaults
# (these match the ctx.env defaults in app/snowflake.yml)
DB="${GIT_SIS_DATABASE:-SNOWFLAKE_LEARNING_DB}"
SCHEMA="${GIT_SIS_SCHEMA:-GIT_SIS}"
APP_NAME="${GIT_SIS_APP_NAME:-INGEST_CONSOLE}"
APP_FQN="$DB.$SCHEMA.$APP_NAME"

info "Deploying via snow streamlit deploy (connection: $CONN) ..."
info "Target: $APP_FQN"
info "Config: $APP_DIR/snowflake.yml"

snow streamlit deploy \
    -c "$CONN" \
    -p "$APP_DIR" \
    --replace

success "Deployed: $APP_FQN"

# Optional: commit live version as a named alias (BCR-1888 / 2025_01 bundle).
# Gives you a stable fallback version separate from the mutable live version.
# Safe on older accounts: commits the live state under the given alias name.
if [[ -n "$COMMIT_ALIAS" ]]; then
    info "Committing live version as '$COMMIT_ALIAS' ..."
    if snow sql -c "$CONN" -q \
        "ALTER STREAMLIT ${APP_FQN} COMMIT VERSION ${COMMIT_ALIAS};" 2>/dev/null; then
        success "Version '$COMMIT_ALIAS' committed. Use ALTER STREAMLIT ... SET DEFAULT_VERSION to pin it."
    else
        warn "--commit skipped: ALTER STREAMLIT COMMIT requires the 2025_01 BCR bundle."
        warn "Enable at: https://docs.snowflake.com/en/release-notes/bcr-bundles/2025_01/bcr-1888"
    fi
fi

info "Run 'scripts/40_verify.sh' to confirm and get the URL."
