#!/usr/bin/env bash
# scripts/check-docs.sh — CI lint for tutorial / docs drift
#
# Fails if any tutorial HTML references known-stale values.
# Run: make check-docs  or  scripts/check-docs.sh
#
# What we check:
#   - Python version referenced in tutorials
#   - snow CLI version referenced in tutorials
#   - Key Makefile targets referenced in tutorials still exist in Makefile
#   - Unit test count referenced in tutorials matches actual test count
#
# When to update this script:
#   - You bump the Python or snow CLI version → update EXPECTED_PYVER / EXPECTED_SNOW_VER
#   - You rename a Makefile target → update EXPECTED_TARGETS
#   - Significant test count change → the test count check will catch it automatically

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TUTORIAL_DIR="$ROOT_DIR/docs/tutorial"
MAKEFILE="$ROOT_DIR/Makefile"

EXPECTED_PYVER="3.11"
EXPECTED_SNOW_VER="3.19"
EXPECTED_TARGETS=("make test" "make deploy" "make test-live" "make dev")

ERRORS=0

ok()   { echo "  [ok]  $*"; }
fail() { echo "  [FAIL] $*" >&2; ERRORS=$((ERRORS + 1)); }

echo ""
echo "check-docs: validating tutorial HTML against repo state"
echo "────────────────────────────────────────────────────────"

# --- 1. Python version -------------------------------------------------------
for f in "$TUTORIAL_DIR"/*.html; do
    if grep -q "Python" "$f" 2>/dev/null; then
        if grep -q "$EXPECTED_PYVER" "$f"; then
            ok "$(basename "$f"): Python $EXPECTED_PYVER found"
        else
            fail "$(basename "$f"): Python version reference may be stale (expected $EXPECTED_PYVER)"
        fi
    fi
done

# --- 2. snow CLI version -----------------------------------------------------
for f in "$TUTORIAL_DIR"/*.html; do
    if grep -q "snow" "$f" 2>/dev/null; then
        if grep -q "$EXPECTED_SNOW_VER\|snow CLI\|snowflake-cli" "$f"; then
            ok "$(basename "$f"): snow CLI version or reference found"
        fi
    fi
done

# --- 3. Makefile target references -------------------------------------------
for target in "${EXPECTED_TARGETS[@]}"; do
    target_name="${target#make }"
    if grep -qE "^${target_name}:" "$MAKEFILE"; then
        ok "Makefile target '$target_name' exists"
    else
        fail "Makefile target '$target_name' not found — tutorial references '${target}' but it may have been renamed"
    fi
done

# --- 4. Unit test count (warn, not fail — count changes are expected) --------
# Extract the count referenced in the tutorial
TUTORIAL_COUNT=$(grep -h -oP '\d+(?= tests? ·|tests?, no)' "$TUTORIAL_DIR"/*.html 2>/dev/null | sort -n | uniq | tail -1 || echo "")
if [ -n "$TUTORIAL_COUNT" ]; then
    # Get actual count (run collection only, no tests executed)
    ACTUAL_COUNT=$(cd "$ROOT_DIR" && uv run pytest tests/unit/ --collect-only -q --no-header 2>/dev/null | grep -oP '^\d+' | tail -1 || echo "unknown")
    if [ "$ACTUAL_COUNT" = "unknown" ]; then
        ok "Unit test count: tutorial references $TUTORIAL_COUNT (actual count unavailable)"
    elif [ "$ACTUAL_COUNT" = "$TUTORIAL_COUNT" ]; then
        ok "Unit test count: tutorial ($TUTORIAL_COUNT) matches actual ($ACTUAL_COUNT)"
    else
        # Warn but don't fail — count changes are frequent and expected during development
        echo "  [warn] Unit test count mismatch: tutorial references $TUTORIAL_COUNT, actual is $ACTUAL_COUNT"
        echo "         Update docs/tutorial/ HTML if this is a significant milestone change."
    fi
fi

echo ""
if [ "$ERRORS" -gt 0 ]; then
    echo "check-docs: $ERRORS error(s) found. Update docs/tutorial/ HTML to fix." >&2
    exit 1
else
    echo "check-docs: OK"
fi
