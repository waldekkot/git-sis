#!/usr/bin/env bash
# lib/_lib.sh -- shared helpers sourced by all git-sis scripts.
# Do NOT execute directly.

set -euo pipefail

# ---- Version (read from root pyproject.toml) --------------------------------
_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_ROOT_DIR="$(dirname "$_SCRIPT_DIR")"   # parent of lib/ = project root

VERSION=$(grep -m1 '^version' "$_ROOT_DIR/pyproject.toml" | grep -o '"[^"]*"' | tr -d '"')
SCRIPT_NAME="$(basename "${BASH_SOURCE[1]:-$0}")"

# ---- Default Snowflake connection -------------------------------------------
CONN="${SNOWFLAKE_DEFAULT_CONNECTION_NAME:-oregon-sedemo}"

# ---- Shared option parsers --------------------------------------------------
handle_version() {
    echo "git-sis $VERSION ($SCRIPT_NAME)"
    exit 0
}

handle_help() {
    # Callers must define a show_help function before calling parse_common_args.
    show_help
    exit 0
}

# Parse --version / --help / -c / --connection from "$@".
# Stores unrecognised arguments in the global REMAINING_ARGS array.
# Runs in the CALLING process (not a subshell) so exit 0 works correctly.
#
# Usage:
#   parse_common_args "$@"
#   set -- "${REMAINING_ARGS[@]+"${REMAINING_ARGS[@]}"}"
REMAINING_ARGS=()
parse_common_args() {
    REMAINING_ARGS=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --version)        handle_version ;;
            -h|--help)        handle_help ;;
            -c|--connection)  shift; CONN="$1" ;;
            *)                REMAINING_ARGS+=("$1") ;;
        esac
        shift
    done
}

# ---- Colour helpers ---------------------------------------------------------
info()    { printf '\033[0;34m[info]\033[0m  %s\n' "$*"; }
success() { printf '\033[0;32m[ok]  \033[0m  %s\n' "$*"; }
warn()    { printf '\033[0;33m[warn]\033[0m  %s\n' "$*" >&2; }
die()     { printf '\033[0;31m[err] \033[0m  %s\n' "$*" >&2; exit 1; }
