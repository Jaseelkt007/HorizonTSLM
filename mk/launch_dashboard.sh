#!/usr/bin/env bash
set -e

# Determine script and repo directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[*] Launching Kelmarsh SCADA Visual Inspector from mk/..."
cd "$REPO_DIR"
uv run streamlit run mk/app.py
