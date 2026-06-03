#!/usr/bin/env bash
# 10_setup.sh -- one-time environment setup: infra database + GIT_SIS schema + tables.
#
# Normal usage (creates infra DB + tables):
#   scripts/10_setup.sh
#
# With git wiring for Snowsight workspace git-sync (optional):
#   scripts/10_setup.sh --with-git
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#       --with-git          Also create API integration + GIT REPOSITORY object.
#                           Needed only for workspace git-sync; NOT required for
#                           snow streamlit deploy (step 30) or CI.
#                           Requires ACCOUNTADMIN access.
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

WITH_GIT=false

show_help() {
    cat <<EOF
git-sis $VERSION -- 10_setup

One-time setup: creates the permanent infra database (for the GitHub PAT secret)
and the GIT_SIS schema with ORDERS + INGEST_LOG tables.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --with-git          Also wire GIT REPOSITORY + API integration for
                            Snowsight workspace git-sync (ACCOUNTADMIN required)
    -h, --help              Show this help text
        --version           Print version and exit

STEPS
    deploy/01_setup_infra.sql   Creates GIT_SIS_INFRA database + SECRETS schema.
                                Holds the GitHub PAT secret permanently (survives
                                90_cleanup.sh resets).
    deploy/00_setup_env.sql     Creates SNOWFLAKE_LEARNING_DB.GIT_SIS schema,
                                ORDERS table, INGEST_LOG table.

    With --with-git, also runs:
    deploy/10_git_and_streamlit.sql (sections 1+2 only: API integration + GIT REPOSITORY)
    Requires a GitHub PAT already stored in GIT_SIS_INFRA.SECRETS.GITHUB_PAT.

EXAMPLES
    # Minimal setup (tables only, deploy via snow streamlit deploy)
    scripts/10_setup.sh

    # Full setup including git wiring for workspace git-sync
    scripts/10_setup.sh --with-git

    # After setup, create the GitHub PAT secret (run once):
    snow sql -c oregon-sedemo -q "
      CREATE OR REPLACE SECRET GIT_SIS_INFRA.SECRETS.GITHUB_PAT
          TYPE = PASSWORD USERNAME = 'waldekkot' PASSWORD = '<pat>';"

NEXT STEP
    scripts/20_run-local.sh   -- verify the app works locally
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-git) WITH_GIT=true ;;
        *) die "Unknown argument: $1. Run with --help for usage." ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

info "Step 1/2 -- infra database (connection: $CONN) ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/01_setup_infra.sql"

info "Step 2/2 -- GIT_SIS schema + tables (connection: $CONN) ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/00_setup_env.sql"

if [[ "$WITH_GIT" == true ]]; then
    warn "--with-git: creating API integration + GIT REPOSITORY (requires ACCOUNTADMIN)."
    warn "Ensure GIT_SIS_INFRA.SECRETS.GITHUB_PAT exists first."
    DB="SNOWFLAKE_LEARNING_DB"
    SCHEMA="GIT_SIS"
    REPO="$DB.$SCHEMA.APP_REPO"
    snow sql -c "$CONN" -q "
        USE ROLE ACCOUNTADMIN;
        CREATE API INTEGRATION IF NOT EXISTS git_api_waldekkot
            API_PROVIDER = git_https_api
            API_ALLOWED_PREFIXES = ('https://github.com/waldekkot')
            ALLOWED_AUTHENTICATION_SECRETS = (GIT_SIS_INFRA.SECRETS.GITHUB_PAT)
            ENABLED = TRUE;
        GRANT USAGE ON INTEGRATION git_api_waldekkot TO ROLE SYSADMIN;
        USE ROLE SYSADMIN;
        CREATE GIT REPOSITORY IF NOT EXISTS $REPO
            API_INTEGRATION = git_api_waldekkot
            GIT_CREDENTIALS = GIT_SIS_INFRA.SECRETS.GITHUB_PAT
            ORIGIN = 'https://github.com/waldekkot/git-sis';
        ALTER GIT REPOSITORY $REPO FETCH;
    "
    success "Git wiring complete: APP_REPO ready for workspace git-sync."
fi

success "Setup complete. Schema, tables, and infra database are ready."
info "Next: scripts/20_run-local.sh (local verify) or scripts/30_deploy.sh (deploy to SiS)"
