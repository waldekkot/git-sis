#!/usr/bin/env bash
# 10_setup.sh -- one-time environment setup: GIT_SIS schema + tables.
#
# Normal usage (creates schema + tables, ready for local dev and deploy):
#   scripts/10_setup.sh
#
# With git wiring for Snowsight workspace git-sync (optional):
#   scripts/10_setup.sh --with-git
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'default')
#       --with-git          Also create API integration + GIT REPOSITORY object.
#                           Uses Snowflake GitHub App OAuth2 -- no PAT required.
#                           Requires ACCOUNTADMIN access.
#                           After setup: authorize the GitHub App in Snowsight
#                           (one-time per user) before running make deploy-git.
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

WITH_GIT=false

show_help() {
    cat <<EOF
git-sis $VERSION -- 10_setup

One-time setup: creates the GIT_SIS schema with ORDERS + INGEST_LOG tables.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --with-git          Also wire GIT REPOSITORY + API integration for
                            Snowsight workspace git-sync and make deploy-git.
                            Uses Snowflake GitHub App OAuth2 (ACCOUNTADMIN required).
                            After running: open Snowsight → any Workspace → Files
                            tab → "Connect Git Repository" and authorize the
                            Snowflake GitHub App.  One-time per user; no PAT needed.
    -h, --help              Show this help text
        --version           Print version and exit

STEPS
    deploy/00_setup_env.sql     Creates SNOWFLAKE_LEARNING_DB.GIT_SIS schema,
                                ORDERS table, INGEST_LOG table.

    With --with-git, also creates:
      API integration git_api_waldekkot  (TYPE = SNOWFLAKE_GITHUB_APP, ACCOUNTADMIN)
      GIT REPOSITORY APP_REPO            (ORIGIN = github.com/waldekkot/git-sis)

EXAMPLES
    # Minimal setup (tables only, deploy via snow streamlit deploy)
    scripts/10_setup.sh

    # Full setup including git wiring for workspace git-sync / make deploy-git
    scripts/10_setup.sh --with-git

NEXT STEP
    scripts/20_run-local.sh   -- verify the app works locally
    scripts/30_deploy.sh      -- push-based deploy to SiS (no git wiring needed)
    make deploy-git           -- pull-based deploy (requires --with-git + OAuth auth)
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

info "GIT_SIS schema + tables (connection: $CONN) ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/00_setup_env.sql"

if [[ "$WITH_GIT" == true ]]; then
    warn "--with-git: creating API integration + GIT REPOSITORY (requires ACCOUNTADMIN)."
    DB="SNOWFLAKE_LEARNING_DB"
    SCHEMA="GIT_SIS"
    REPO="$DB.$SCHEMA.APP_REPO"
    snow sql -c "$CONN" -q "
        USE ROLE ACCOUNTADMIN;
        CREATE API INTEGRATION IF NOT EXISTS git_api_waldekkot
            API_PROVIDER = git_https_api
            API_ALLOWED_PREFIXES = ('https://github.com/waldekkot')
            API_USER_AUTHENTICATION = (TYPE = SNOWFLAKE_GITHUB_APP)
            ENABLED = TRUE;
        GRANT USAGE ON INTEGRATION git_api_waldekkot TO ROLE SYSADMIN;
        USE ROLE SYSADMIN;
        CREATE GIT REPOSITORY IF NOT EXISTS $REPO
            API_INTEGRATION = git_api_waldekkot
            ORIGIN = 'https://github.com/waldekkot/git-sis';
    "
    success "Git wiring complete: API integration + APP_REPO created."
    echo ""
    warn "ACTION REQUIRED (one-time per user):"
    warn "  Before make deploy-git will work, authorize the Snowflake GitHub App:"
    warn "  1. Open Snowsight → Projects → any Workspace"
    warn "  2. In the Files tab select 'Connect Git Repository'"
    warn "  3. Complete the GitHub OAuth authorization"
    warn "  After that, 'make deploy-git' and FETCH commands will work from CLI too."
    echo ""
    # Attempt FETCH -- succeeds if user has already authorized, or if this is
    # the first time (will fail gracefully with auth instructions above).
    if snow sql -c "$CONN" -q "ALTER GIT REPOSITORY $REPO FETCH;" 2>/dev/null; then
        success "Repository fetched successfully."
    else
        warn "FETCH skipped -- complete the OAuth authorization above first."
        warn "Then run: snow sql -c $CONN -q \"ALTER GIT REPOSITORY $REPO FETCH;\""
    fi
fi

success "Setup complete. Schema, tables, and infra database are ready."
info "Next: scripts/20_run-local.sh (local verify) or scripts/30_deploy.sh (deploy to SiS)"
