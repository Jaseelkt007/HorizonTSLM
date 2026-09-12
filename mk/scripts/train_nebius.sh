#!/usr/bin/env bash
set -e

echo "========================================================================"
echo "    ETH Agentic Systems Lab X Aionic Labs X Nebius Hackathon"
echo "    WindTurbine-TSLM: Training Pipeline on Nebius H100 GPU"
echo "========================================================================"

# 1. Ensure uv is installed
if ! command -v uv &> /dev/null; then
    echo "[*] Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.cargo/env" || export PATH="$HOME/.local/bin:$PATH"
fi

# 2. Synchronize virtual environment
echo "[*] Installing dependencies with uv..."
uv sync

# 3. Build and register Kelmarsh dataset with TimeNet
echo "[*] Ingesting and publishing Kelmarsh SCADA data to TimeNet registry..."
uv run python scripts/build_timenet.py --force

# 4. Train OpenTSLM on Nebius GPU
echo "[*] Launching OpenTSLM training on GPU..."
DEVICE="cuda"
if ! nvidia-smi &> /dev/null; then
    echo "[!] No NVIDIA GPU detected, falling back to auto device selection."
    DEVICE=""
fi

if [ -n "$DEVICE" ]; then
    uv run python src/models/train.py --epochs 25 --batch-size 16 --lr 3e-4 --device cuda
else
    uv run python src/models/train.py --epochs 10 --batch-size 8 --lr 3e-4
fi

# 5. Run zero-leakage benchmark vs baselines
echo "[*] Evaluating OpenTSLM vs Classical ML & Text LLM baselines on held-out Turbine 6..."
uv run python -m src.evaluation.evaluate

echo "========================================================================"
echo "[+] Training and evaluation complete!"
echo "[+] Checkpoints saved in checkpoints/opentslm_best.pt"
echo "[+] Benchmark tables saved in results/benchmark_table.md"
echo ""
echo "To launch the live interactive jury dashboard:"
echo "  uv run streamlit run demo/app.py --server.port 8501"
echo "========================================================================"
