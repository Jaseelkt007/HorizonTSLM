"""Entrypoint for Wind Turbine SCADA Visualizers in mk/.

Provides navigation between:
1. 🔍 SCADA Data Inspection Visualizer (Turbine data, date/time picker, SCADA events, turbine comparison, baselines)
2. ⚡ Model Diagnostic & Fleet Visualizer (OpenTSLM diagnostic reports, fleet health, power curves)
"""

import sys
from pathlib import Path
import streamlit as st

# Add repo root and mk/ to sys.path
_curr = Path(__file__).resolve().parent
REPO_ROOT = _curr.parent if (_curr.parent / "pyproject.toml").exists() else _curr

for p in [REPO_ROOT, _curr]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    st.set_page_config(
        page_title="Wind Turbine SCADA Workbench",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

try:
    import mk.data_inspection as data_inspection_mod
    import mk.dashboard as dashboard_mod
except ImportError:
    import data_inspection as data_inspection_mod
    import dashboard as dashboard_mod


def main():
    # Top-level switcher in sidebar
    st.sidebar.markdown("### 🎛️ Application Workspace")
    app_mode = st.sidebar.radio(
        "Select Visualizer:",
        [
            "🔍 SCADA Data Inspection",
            "⚡ Model Diagnostic & Fleet Overview",
        ],
        index=0,
    )
    st.sidebar.markdown("---")

    if app_mode == "🔍 SCADA Data Inspection":
        data_inspection_mod.main()
    else:
        dashboard_mod.main()


if __name__ == "__main__":
    main()
