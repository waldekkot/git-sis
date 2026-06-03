#!/usr/bin/env bash
# 90_cleanup.sh -- reset the demo (keeps GIT_SIS_INFRA + GitHub PAT secret).
#
# Drops: STREAMLIT object, GIT REPOSITORY, GIT_SIS schema (CASCADE), API integration.
# Keeps: GIT_SIS_INFRA database and SECRETS.GITHUB_PAT (permanent credential store).
#
# After running, the demo can be rebuilt with:
#   scripts/10_setup.sh && scripts/30_deploy.sh
# No need to re-enter the GitHub PAT -- it survived the reset.
#
# For FULL teardown (drops GIT_SIS_INFRA too), use:
#   scripts/99_cleanup-infra.sh
#
# Usage:
#   scripts/90_cleanup.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

show_help() {
    cat <<EOF
git-sis $VERSION -- 90_cleanup

Resets the demo by dropping GIT_SIS schema (+ STREAMLIT, GIT REPOSITORY,
API integration). The GIT_SIS_INFRA database and GITHUB_PAT secret survive.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
    -h, --help              Show this help text
        --version           Print version and exit

WHAT IS DROPPED
    SNOWFLAKE_LEARNING_DB.GIT_SIS.*  (schema CASCADE: tables, STREAMLIT, GIT REPOSITORY)
    git_api_waldekkot                (API integration, ACCOUNTADMIN required)

WHAT SURVIVES
    GIT_SIS_INFRA.SECRETS.GITHUB_PAT   (permanent -- no re-entry needed on rebuild)

REBUILD
    scripts/10_setup.sh && scripts/30_deploy.sh

FULL TEARDOWN (also drops infra DB + secret)
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
warn "GIT_SIS_INFRA.SECRETS.GITHUB_PAT will be preserved."

snow sql -c "$CONN" -f "$ROOT_DIR/deploy/99_cleanup.sql"

success "Demo reset complete. GIT_SIS_INFRA.SECRETS.GITHUB_PAT is intact."
info "Rebuild anytime: scripts/10_setup.sh && scripts/30_deploy.sh"
