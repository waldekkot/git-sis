#!/usr/bin/env bash
# 99_cleanup-infra.sh -- FULL teardown: drops everything including API integration.
#
# With Snowflake GitHub App OAuth2 there is no longer a separate infra database
# or PAT secret to manage.  This script is now equivalent to 90_cleanup.sh
# but retains the confirmation prompt as a safety gate for complete decommissioning.
#
# Only use when completely decommissioning the demo.
#
# Usage:
#   scripts/99_cleanup-infra.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'default')
#       --yes               Skip the confirmation prompt
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

SKIP_CONFIRM=false

show_help() {
    cat <<EOF
git-sis $VERSION -- 99_cleanup-infra

FULL teardown: drops everything -- GIT_SIS schema (CASCADE), STREAMLIT,
GIT REPOSITORY, and the API integration (git_api_waldekkot).

No separate infra database exists anymore: authentication uses the
Snowflake GitHub App OAuth2 flow -- no PAT to delete.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --yes               Skip the confirmation prompt (for scripted use)
    -h, --help              Show this help text
        --version           Print version and exit

WHAT IS DROPPED
    SNOWFLAKE_LEARNING_DB.GIT_SIS.*  (schema CASCADE: tables, STREAMLIT, GIT REPOSITORY)
    git_api_waldekkot                (API integration, ACCOUNTADMIN required)

REBUILD AFTER THIS
    scripts/10_setup.sh --with-git   # re-creates schema, tables, API integration
    # Then authorize the Snowflake GitHub App in Snowsight (one-time per user)
    scripts/30_deploy.sh

FOR NORMAL RESETS
    scripts/90_cleanup.sh   (same SQL, no confirmation prompt)
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes) SKIP_CONFIRM=true ;;
        *) die "Unknown argument: $1. Run with --help for usage." ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

warn "NUCLEAR: This drops GIT_SIS schema + API integration completely."
warn "For a normal reset, use: scripts/90_cleanup.sh"

if [[ "$SKIP_CONFIRM" == false ]]; then
    printf 'Type YES to confirm full teardown: '
    read -r CONFIRM
    [[ "$CONFIRM" == "YES" ]] || die "Aborted. Nothing was dropped."
fi

info "Full teardown (connection: $CONN) ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/99_cleanup.sql"

success "Full teardown complete."
info "To rebuild: scripts/10_setup.sh --with-git, authorize GitHub App in Snowsight, then scripts/30_deploy.sh"
