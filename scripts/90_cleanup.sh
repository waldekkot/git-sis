#!/usr/bin/env bash
# 90_cleanup.sh -- reset the demo.
#
# Drops: STREAMLIT object, GIT REPOSITORY, GIT_SIS schema (CASCADE), API integration.
# The API integration is dropped but the Snowflake GitHub App OAuth2 authorization
# is preserved in Snowflake -- no re-authorization needed when you rebuild.
#
# After running, the demo can be rebuilt with:
#   scripts/10_setup.sh && scripts/30_deploy.sh        (push-based)
#   scripts/10_setup.sh --with-git && scripts/30_deploy.sh  (+ git wiring)
#
# For a full teardown that also revokes the GitHub App OAuth connection, use:
#   scripts/99_cleanup-infra.sh
#
# Usage:
#   scripts/90_cleanup.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'default')
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

show_help() {
    cat <<EOF
git-sis $VERSION -- 90_cleanup

Resets the demo by dropping GIT_SIS schema (+ STREAMLIT, GIT REPOSITORY,
API integration). Authentication is Snowflake GitHub App OAuth2 -- no PAT
to preserve. Re-running make setup-git restores the API integration.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
    -h, --help              Show this help text
        --version           Print version and exit

WHAT IS DROPPED
    SNOWFLAKE_LEARNING_DB.GIT_SIS.*  (schema CASCADE: tables, STREAMLIT, GIT REPOSITORY)
    git_api_waldekkot                (API integration, ACCOUNTADMIN required)

REBUILD
    scripts/10_setup.sh && scripts/30_deploy.sh

FULL TEARDOWN (revokes GitHub App OAuth connection too)
    scripts/99_cleanup-infra.sh
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
[[ $# -eq 0 ]] || die "Unknown argument: $1. Run with --help for usage."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

info "Resetting demo state (connection: $CONN) ..."
warn "This drops SNOWFLAKE_LEARNING_DB.GIT_SIS and the API integration."

snow sql -c "$CONN" -f "$ROOT_DIR/deploy/99_cleanup.sql"

success "Demo reset complete."
info "Rebuild anytime: scripts/10_setup.sh && scripts/30_deploy.sh"
