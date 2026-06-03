#!/usr/bin/env bash
# run-local.sh -- launch the Ingestion Ops Console locally.
#
# Usage:
#   scripts/run-local.sh [options]
#
# Options:
#   -c, --connection NAME   Snowflake CLI connection to use
#                           (default: $SNOWFLAKE_DEFAULT_CONNECTION_NAME or 'oregon-sedemo')
#   -p, --port PORT         Streamlit server port  [default: 8501]
#   -h, --help              Show this help text
#       --version           Print version and exit

set -euo pipefail
source "$(dirname "$0")/_lib.sh"

PORT=8501

show_help() {
    cat <<EOF
git-sis $VERSION -- run-local

Runs the Streamlit app on your laptop against a real Snowflake connection.
Uses the dual-mode session seam: sets SNOWFLAKE_DEFAULT_CONNECTION_NAME so
lib/session.py falls back to Session.builder (the local path).

USAGE
    $(basename "$0") [OPTIONS]

OPTIONS
    -c, --connection NAME   Snowflake CLI connection  [default: $CONN]
    -p, --port PORT         Streamlit server port     [default: $PORT]
    -h, --help              Show this help text
        --version           Print version and exit

EXAMPLES
    # Default connection, default port
    scripts/run-local.sh

    # Custom port
    scripts/run-local.sh -p 8533

    # Different connection
    scripts/run-local.sh -c my-other-conn
EOF
}

parse_common_args "$@"
set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--port) shift; PORT="$1" ;;
        *) die "Unknown argument: $1. Run with --help for usage." ;;
    esac
    shift
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

info "Starting Ingestion Ops Console (connection: $CONN, port: $PORT) ..."
info "Open: http://localhost:$PORT"
export SNOWFLAKE_DEFAULT_CONNECTION_NAME="$CONN"
exec uv run --project "$ROOT_DIR" streamlit run \
    "$ROOT_DIR/app/streamlit_app.py" \
    --server.port "$PORT" \
    --server.headless false
