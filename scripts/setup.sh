#!/usr/bin/env bash
# setup.sh -- create the DEV schema and tables in Snowflake.
#
# Usage:
#   scripts/setup.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection to use
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

show_help() {
    cat <<EOF
git-sis $VERSION -- setup

Creates the SNOWFLAKE_LEARNING_DB.GIT_SIS schema, ORDERS table, and
INGEST_LOG table using deploy/00_setup_env.sql.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
    -h, --help              Show this help text
        --version           Print version and exit

EXAMPLES
    # Use the default connection (oregon-sedemo)
    scripts/setup.sh

    # Use a different connection
    scripts/setup.sh -c my-prod-conn
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"

[[ $# -eq 0 ]] || die "Unknown argument: $1. Run with --help for usage."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

info "Setting up Snowflake environment (connection: $CONN) ..."
snow sql -c "$CONN" -f "$ROOT_DIR/deploy/00_setup_env.sql"
success "Schema and tables created."
