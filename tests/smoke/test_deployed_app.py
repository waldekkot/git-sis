"""Smoke tests — verify the deployed SiS app is live and healthy.

Run after deploy (in CI or manually):
    GIT_SIS_APP_URL=<url> uv run pytest tests/smoke/ -v

Or via make:
    make test-smoke          # uses GIT_SIS_APP_URL env var
    make test-smoke CONN=ci  # capture URL from snow streamlit get-url first

All tests are skipped automatically when GIT_SIS_APP_URL is not set, so
they never accidentally block unit or integration test runs.

These tests are intentionally READ-ONLY and SIDE-EFFECT-FREE:
- No SQL writes
- No Snowflake credentials required (tests hit the public HTTPS endpoint)
- Safe to run against production

Tier in the testing pyramid:
    Ring 1  unit tests       (emulator, ~2s, no credentials)
    Ring 2  integration      (real Snowflake, isolated schema, ~60s)
    Ring 3  smoke  ← THIS   (deployed app, HTTPS only, ~5s)
"""

from __future__ import annotations

import os

import httpx
import pytest

APP_URL = os.getenv("GIT_SIS_APP_URL", "")

skip_no_url = pytest.mark.skipif(
    not APP_URL,
    reason="GIT_SIS_APP_URL not set — set it to the deployed app URL to run smoke tests",
)


@skip_no_url
def test_app_responds_200() -> None:
    """Deployed app returns HTTP 200 within the timeout window."""
    resp = httpx.get(APP_URL, follow_redirects=True, timeout=30)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"


@skip_no_url
def test_app_is_streamlit() -> None:
    """Response body contains Streamlit fingerprint (JS bundle reference)."""
    resp = httpx.get(APP_URL, follow_redirects=True, timeout=30)
    assert resp.status_code == 200
    # Snowsight-hosted Streamlit apps embed a reference to the Streamlit JS
    # bundle in the HTML. This confirms it's a real app, not a redirect/error page.
    assert "streamlit" in resp.text.lower(), "Response does not look like a Streamlit app"


@skip_no_url
def test_app_title_present() -> None:
    """Page HTML contains the app's expected title."""
    resp = httpx.get(APP_URL, follow_redirects=True, timeout=30)
    assert resp.status_code == 200
    # Snowsight sets the browser <title> from the app's TITLE property.
    assert "ingest" in resp.text.lower() or "console" in resp.text.lower(), (
        "Expected app title ('Ingest' or 'Console') not found in response"
    )
