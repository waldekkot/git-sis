"""Metric KPI components.

Shared tile renderers used by streamlit_app.py and any page that displays
headline KPIs. All functions are stateless — no session, no SQL.
"""

from __future__ import annotations

from typing import Literal

import streamlit as st

DeltaColor = Literal["normal", "inverse", "off"]


def render_kpi_card(
    label: str,
    value: str | int | float,
    delta: str | None = None,
    delta_color: DeltaColor = "normal",
    help: str | None = None,
) -> None:
    """Render a single KPI metric tile.

    Thin wrapper around st.metric that gives a consistent call signature
    across all pages and makes the intent explicit in test assertions.

    Args:
        label:        KPI label displayed above the value.
        value:        The headline number or string to display.
        delta:        Optional delta annotation (e.g. "+3 vs yesterday").
        delta_color:  "normal" | "inverse" | "off" — passed to st.metric.
        help:         Optional tooltip text.

    Example:
        render_kpi_card("Total runs", kpis["total_runs"], help="All-time run count")
    """
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help,
    )
