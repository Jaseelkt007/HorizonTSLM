#!/usr/bin/env bash
set -e

# Launch Kelmarsh SCADA Streamlit dashboard
echo "[*] Starting Kelmarsh SCADA Dataset Visual Inspector..."
uv run streamlit run app.py
