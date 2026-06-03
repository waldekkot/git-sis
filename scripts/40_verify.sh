#!/usr/bin/env bash
# 40_verify.sh -- confirm the deployed app exists and print its URL.
#
# Usage:
#   scripts/40_verify.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#       --open              Open the app URL in the default browser
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/../lib/_lib.sh"

OPEN_BROWSER=false

show_help() {
    cat <<EOF
git-sis $VERSION -- 40_verify

Checks that SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE exists in the
account and prints its Snowsight URL.

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
        --open              Open the URL in your default browser
    -h, --help              Show this help text
        --version           Print version and exit

EXAMPLES
    scripts/40_verify.sh
    scripts/40_verify.sh --open
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --open) OPEN_BROWSER=true ;;
        *) die "Unknown argument: $1. Run with --help for usage." ;;
    esac
    shift
done

APP="SNOWFLAKE_LEARNING_DB.GIT_SIS.INGEST_CONSOLE"

info "Checking Streamlit object exists (connection: $CONN) ..."
snow sql -c "$CONN" -q \
    "SHOW STREAMLITS LIKE 'INGEST_CONSOLE' IN SCHEMA SNOWFLAKE_LEARNING_DB.GIT_SIS;"

URL=$(snow streamlit get-url -c "$CONN" "$APP" 2>&1) || \
    die "Could not get URL -- is the app deployed? Run scripts/30_deploy.sh first."

success "App is live."
echo ""
echo "  URL: $URL"
echo ""

if [[ "$OPEN_BROWSER" == true ]]; then
    info "Opening in browser ..."
    open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null || \
        warn "Could not auto-open browser. Visit the URL above manually."
fi
