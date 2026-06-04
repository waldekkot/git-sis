"""Shared UI components — stateless render functions.

Layer rules
-----------
CAN  import streamlit  (this IS a UI layer; sits above lib.ingest + lib.config)
MUST NOT import lib.ingest or lib.config directly (data flows in via arguments)
MUST be side-effect-free except for st.* widget calls
SHOULD accept data as plain Python / pandas arguments; return None

Why a separate layer?
    Without lib/components/, shared display logic gets copy-pasted across
    pages/ files. A component function is importable, testable in isolation,
    and a single place to update when design changes.

Testing
-------
Components are testable with AppTest.from_function:

    from lib.components.metrics import render_kpi_card
    from streamlit.testing.v1 import AppTest

    def test_kpi_card():
        at = AppTest.from_function(
            lambda: render_kpi_card("Total runs", 42, delta="+3")
        ).run()
        assert at.metric[0].value == "42"

Architecture diagram (full 4-layer model)
------------------------------------------
    lib/config.py           table FQNs (env-var overridable)
         ↓ imported by
    lib/ingest.py           Snowpark DataFrame logic (Streamlit-free)
         ↓ data passed via args to
    lib/components/         shared UI components (CAN import streamlit)
         ↓ called from
    lib/session.py          session seam (only file with @st.cache_resource)
    pages/*, streamlit_app.py   thin UI orchestration

Importlinter contracts (app/.importlinter)
------------------------------------------
  lib.ingest + lib.config  → forbidden: streamlit
  lib.components           → forbidden: lib.ingest, lib.config
                             (data must flow in through arguments, not imports)
"""
