# MK Visual Interface & Telemetry Inspector

This directory contains the visual interface tools for inspecting, exploring, and analyzing the Kelmarsh wind farm SCADA dataset (`energy/kelmarsh-wind-scada`).

## Contents

- `app.py`: Streamlit entrypoint.
- `dashboard.py`: Core interactive dashboard featuring:
  - **🛰️ Fleet Overview & Map**: Geographic map of 6 Senvion MM92 turbines (UK), rated capacity (2.05 MW each), asset specs, and fault distributions.
  - **📈 Telemetry Window Inspector**: Synchronized Plotly charts across all 8 continuous sensors (Aerodynamics, Drivetrain Mechanics, Thermal signatures) over 12-hour windows (72 steps @ 10-min resolution).
  - **🧠 AI Diagnostics & Chain-of-Thought**: Supervisory LLM prompts, detailed physical reasoning rationales, and recommended maintenance interventions.
  - **🌪️ Power Curve & Analytics**: Real SCADA active power generation vs theoretical 2,050 kW Senvion MM92 power curve, cross-sensor scatters, and correlation heatmaps.
  - **⚖️ Anomaly Comparison**: Residual comparison ($\Delta = \text{Fault} - \text{Normal}$) isolating anomaly signatures.
  - **💾 Raw Data & Export**: Complete telemetry matrix with 1-click CSV download.
- `launch_dashboard.sh`: Convenience launcher script.
- `dataset_explorer.html`: Self-contained standalone HTML visual interface (open directly in any web browser).
- `test_visualization.py`: Automated pytest test suite.

---

## How to Run

### 1. Interactive Streamlit App
From the repository root:
```bash
uv run streamlit run mk/app.py
```
or run the launcher script:
```bash
./mk/launch_dashboard.sh
```
Then open `http://localhost:8501` in your browser.

### 2. Standalone HTML Explorer
Open `mk/dataset_explorer.html` directly in any web browser:
```bash
open mk/dataset_explorer.html
```

### 3. Run Automated Tests
```bash
uv run pytest mk/tests/test_visualization.py -v
```
