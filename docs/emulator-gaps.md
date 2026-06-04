# Snowpark Local-Testing Emulator — Known Gaps

The unit-test inner loop (`make test`, ~2s, zero credentials) runs business logic
against the **Snowpark local-testing emulator** (`Session.builder.config("local_testing",
True)`). The emulator implements most of the DataFrame API but a handful of Snowflake
built-ins and behaviours are missing. This table is the single source of truth for *what
we patch and why* — so "works locally, breaks live" never becomes tribal knowledge.

> **Golden rule (WAYS-OF-WORKING §1.3):** mock only what the emulator cannot provide;
> inject everything that is configurable (the session). Never `MagicMock` business logic.

## Gap inventory

| Gap | Symptom in emulator | How we handle it | Where |
|---|---|---|---|
| `UNIFORM(low, high, gen)` | Not implemented | `@snowflake.snowpark.mock.patch` → `_mock_uniform` (int bounds → int, float → float) | `tests/unit/conftest.py` |
| `ROUND(value, scale)` | Not implemented | `@snowflake.snowpark.mock.patch` → `_mock_round` | `tests/unit/conftest.py` |
| `UUID_STRING()` via `call_function` | Not implemented | `uuid_patch` fixture: `unittest.mock` → `lit(str(uuid.uuid4()))` | `tests/unit/conftest.py` |
| `session.sql(...)` | Raw SQL not supported | **Architectural**: `lib/ingest.py` uses the DataFrame API exclusively — no `session.sql()` in app code | `app/lib/ingest.py` |
| `current_timestamp()` semantics | Works, but not wall-clock deterministic | Assert on row counts / status, not exact timestamps | tests |
| pandas compat warning | `UserWarning` from `snowflake.snowpark.mock` | Suppressed via `filterwarnings` | `pyproject.toml` |

### Patch types — which tool for which gap

- **`@snowflake.snowpark.mock.patch`** (preferred): for missing *Snowflake functions*
  (`uniform`, `round`). It plugs into the emulator's function registry and receives
  `ColumnEmulator`/literal args exactly as Snowflake would.
- **`unittest.mock.patch`**: only for `call_function("UUID_STRING")` — a built-in the
  emulator's registry can't express. Patched at the `lib.ingest.call_function` seam.
- **`MagicMock`**: permitted in exactly two places — `test_session.py` (testing the seam
  itself) and the single "session fails" test (controlled inaccessible tables). Never for
  happy-path logic.

## The safety net: cross-validate against real Snowflake

Because the emulator is an approximation, **every emulator gap is a potential
local-vs-live divergence.** Two guards close that gap:

1. **`make test-live`** — runs the *same unit tests* against a real Snowflake connection
   (disposable `GIT_SIS_TEST_<uuid>` schema). If a patch masks a real-engine difference,
   this catches it.
2. **`make test-integration`** — Snowpark integration tests against real Snowflake.

Both are in the PR checklist (`.github/pull_request_template.md`) and `test-integration`
runs in CI on `main`.

## When you hit a NEW gap

1. Confirm it's an emulator limitation (not a logic bug) by running the failing case with
   `make test-live`.
2. Prefer `@snowflake.snowpark.mock.patch` over `unittest.mock`.
3. Add a row to the table above with *symptom → patch → location*.
4. If the gap forces raw SQL, refactor to the DataFrame API instead of adding
   `session.sql()` — that keeps the logic emulator-testable (and import-linter happy).

## Reference
- [Testing Snowpark Python locally](https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally)
- [`snowflake.snowpark.mock.patch`](https://docs.snowflake.com/en/developer-guide/snowpark/python/testing-locally#patching-built-in-functions)
