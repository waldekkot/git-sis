#!/usr/bin/env bash
# 99_cleanup-infra.sh -- FULL teardown: drops GIT_SIS_INFRA database + GitHub PAT secret.
#
# WARNING: This also runs 90_cleanup first (idempotent), then drops the infra
# database. The GitHub PAT is permanently deleted and must be re-entered on rebuild.
#
# Only use when completely decommissioning the demo.
#
# Usage:
#   scripts/99_cleanup-infra.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#       --yes               Skip the confirmation prompt
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

SKIP_CONFIRM=false

show_help() {
    cat <<EOF
git-sis $VERSION -- 99_cleanup-infra

FULL teardown: drops everything, including GIT_SIS_INFRA database and the
GitHub PAT secret. This is the "nuclear option" for complete decommissioning.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --yes               Skip the confirmation prompt (for scripted use)
    -h, --help              Show this help text
        --version           Print version and exit

WHAT IS DROPPED
    Everything from 90_cleanup.sh PLUS:
    GIT_SIS_INFRA.SECRETS.GITHUB_PAT   (GitHub PAT credential)
    GIT_SIS_INFRA.SECRETS              (schema)
    GIT_SIS_INFRA                      (database)

REBUILD AFTER THIS
    scripts/10_setup.sh
    snow sql -c <conn> -q "CREATE OR REPLACE SECRET GIT_SIS_INFRA.SECRETS.GITHUB_PAT ..."
    scripts/30_deploy.sh

FOR NORMAL RESETS (keeps the PAT)
    scripts/90_cleanup.sh
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

warn "NUCLEAR: This drops GIT_SIS_INFRA database + GITHUB_PAT secret."
warn "The PAT will need to be re-entered to rebuild the demo."
warn "For a normal reset (keeping the PAT), use: scripts/90_cleanup.sh"

if [[ "$SKIP_CONFIRM" == false ]]; then
    printf 'Type YES to confirm full teardown: '
    read -r CONFIRM
    [[ "$CONFIRM" == "YES" ]] || die "Aborted. Nothing was dropped."
fi

info "Step 1/2 -- demo reset (connection: $CONN) ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/99_cleanup.sql"

info "Step 2/2 -- infra database + PAT secret ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/98_cleanup_infra.sql"

success "Full teardown complete. GIT_SIS_INFRA has been dropped."
info "To rebuild: scripts/10_setup.sh, then re-create GITHUB_PAT, then scripts/30_deploy.sh"
