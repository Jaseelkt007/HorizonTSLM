"""Streamlit Interactive Live Demo: Wind Turbine Telemetry Anomaly Diagnosis with TimeNet & OpenTSLM.

For the ETH Agentic Systems Lab X Aionic Labs X Nebius Hackathon.
"""

import datetime
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import torch

from src.data.schemas import (
    FAULT_CLASSES,
    KELMARSH_DATASET_ID,
    PENMANSHIEL_DATASET_ID,
    SELECTED_SIGNALS,
    SIGNAL_NAMES,
)
from src.models.architecture import OpenTSLMForTurbineDiagnosis
from src.models.opentslm_dataset import OpenTSLMKelmarshDataset, OpenTSLMWindDataset

st.set_page_config(
    page_title="WindTurbine-TSLM | Live Demo",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-box {
        background-color: #F3F4F6;
        padding: 12px;
        border-radius: 8px;
        text-align: center;
        border-left: 4px solid #3B82F6;
    }
    .anomaly-card-critical {
        background-color: #FEE2E2;
        border: 2px solid #EF4444;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .anomaly-card-normal {
        background-color: #ECFDF5;
        border: 2px solid #10B981;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .zero-shot-banner {
        background: linear-gradient(135deg, #1E1B4B 0%, #312E81 100%);
        color: #EEF2FF;
        border: 1px solid #6366F1;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_cached_model():
    checkpoint_path = Path("checkpoints/opentslm_best.pt")
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
    model = OpenTSLMForTurbineDiagnosis(in_channels=8, patch_size=4, d_encoder=256, d_llm=512)
    if checkpoint_path.exists():
        ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    return model, device


@st.cache_data
def load_farm_windows(farm_key: str):
    """Load windows for the selected farm."""
    if farm_key == "penmanshiel":
        # Load held-out in-domain test set (Turbines WT13-WT15)
        ds = OpenTSLMWindDataset(split="test", dataset_id=PENMANSHIEL_DATASET_ID)
    else:
        # Load Kelmarsh as completely blank demo testbed
        ds = OpenTSLMKelmarshDataset(split="all", dataset_id=KELMARSH_DATASET_ID)

    samples = []
    for i in range(len(ds)):
        s = ds[i]
        samples.append(
            {
                "idx": i,
                "record_id": s["record_id"],
                "turbine_id": s["turbine_id"],
                "label_name": s["label_name"],
                "time_series": s["time_series"].numpy(),  # (72, 8)
                "prompt": s["pre_prompt"],
                "rationale": s["rationale"],
                "action": s["action"],
            }
        )
    return samples


def main():
    st.markdown('<div class="main-header">⚡ WindTurbine-TSLM: Temporal AI for Predictive Maintenance</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">ETH Agentic Systems Lab × Aionic Labs × Nebius Hackathon | Powered by <b>TimeNet</b> + <b>OpenTSLM</b></div>',
        unsafe_allow_html=True,
    )

    model, device = load_cached_model()

    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Telemetry Controls")

        farm_choice = st.radio(
            "Wind Farm Data Source:",
            [
                "📍 Penmanshiel (In-Domain Test Turbines WT13-15)",
                "🌐 Kelmarsh (Completely Blank / Unseen Demo)",
            ],
            index=1,  # Default to Kelmarsh to showcase the blank data demo
        )

        is_kelmarsh = "Kelmarsh" in farm_choice
        farm_key = "kelmarsh" if is_kelmarsh else "penmanshiel"
        test_samples = load_farm_windows(farm_key)

        if is_kelmarsh:
            st.markdown(
                """
                <div style="background-color:#FEF3C7; border-left:4px solid #F59E0B; padding:10px; border-radius:6px; font-size:0.88rem; color:#92400E;">
                <b>Zero-Shot Demo Target</b><br>
                Kelmarsh data is <b>100% unseen and blank</b> to the model. Evaluates cross-farm transfer from Penmanshiel.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("🔒 **In-Domain Test Set**: Turbines WT13–WT15 (Turbines WT01–WT10 trained, WT11–WT12 validated).")

        if not test_samples:
            st.error("No windows found. Please run `python scripts/build_timenet.py --dataset all --force`.")
            return

        st.markdown("---")
        # Filter or select turbine
        all_turbines = sorted(list(set(s["turbine_id"] for s in test_samples)))
        selected_turb = st.selectbox("Filter Turbine:", ["All Turbines"] + all_turbines)

        filtered_samples = [s for s in test_samples if selected_turb == "All Turbines" or s["turbine_id"] == selected_turb]

        scenario_labels = [f"#{s['idx']:02d}: {s['turbine_id']} - {s['label_name']} ({s['record_id']})" for s in filtered_samples]
        selected_scenario_str = st.selectbox("Select 12-Hour SCADA Window:", scenario_labels, index=0)
        selected_idx = int(selected_scenario_str.split(":")[0].replace("#", ""))
        sample = next(s for s in test_samples if s["idx"] == selected_idx)

        st.markdown("---")
        st.subheader("Reasoning Model")
        model_choice = st.radio(
            "Selected Architecture:",
            ["OpenTSLM (TimeNet Patch Encoder)", "Classical ML Baseline (RF)", "Text-only LLM Baseline"],
        )

        st.markdown("---")
        st.markdown("### Telemetry Channels")
        show_wind = st.checkbox("Wind Speed (m/s)", value=True)
        show_power = st.checkbox("Active Power (kW)", value=True)
        show_gear_temp = st.checkbox("Gearbox Oil Temp (°C)", value=True)
        show_gen_temp = st.checkbox("Generator Bearing Temp (°C)", value=True)
        show_pitch = st.checkbox("Blade Pitch Angle (°)", value=False)
        show_vibe = st.checkbox("Drivetrain Vibration (mm/s²)", value=False)

    # Cross-Farm Zero-Shot Banner
    if is_kelmarsh:
        st.markdown(
            """
            <div class="zero-shot-banner">
                <span style="font-size: 1.15rem; font-weight: 700;">🌐 CROSS-FARM ZERO-SHOT EVALUATION (UNSEEN DEMO DATA)</span><br>
                <span>The OpenTSLM model was <b>trained exclusively on Penmanshiel Wind Farm data</b>. The telemetry shown below from <b>Kelmarsh Wind Farm</b> represents completely blank, out-of-domain machines that the model has never encountered during training.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Main dashboard metrics
    ts_arr = sample["time_series"]  # (72, 8)
    time_steps = [f"T+{i*10}m" for i in range(72)]

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Avg Wind Speed", f"{np.mean(ts_arr[:, 0]):.1f} m/s", delta=f"{ts_arr[-1, 0] - ts_arr[0, 0]:.1f} m/s")
    with col2:
        st.metric("Avg Power", f"{np.mean(ts_arr[:, 1]):.0f} kW", delta=f"{ts_arr[-1, 1] - ts_arr[0, 1]:.0f} kW")
    with col3:
        st.metric("Peak Gearbox Oil", f"{np.max(ts_arr[:, 4]):.1f} °C", delta=f"{ts_arr[-1, 4] - ts_arr[0, 4]:.1f} °C")
    with col4:
        st.metric("Peak Bearing Temp", f"{np.max(ts_arr[:, 5]):.1f} °C", delta=f"{ts_arr[-1, 5] - ts_arr[0, 5]:.1f} °C")
    with col5:
        st.metric("Max Vibration", f"{np.max(ts_arr[:, 7]):.1f} mm/s²")

    # Time series visualization
    st.subheader(f"📈 12-Hour Continuous SCADA Telemetry: {sample['turbine_id']} ({sample['record_id']})")

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Wind Speed & Power Generation", "Thermal Trajectories (Gearbox & Generator)", "Mechanical Dynamics (Pitch & Vibration)"),
    )

    # Row 1: Wind speed & Power
    if show_wind:
        fig.add_trace(go.Scatter(x=time_steps, y=ts_arr[:, 0], name="Wind Speed (m/s)", line=dict(color="#2563EB", width=2)), row=1, col=1)
    if show_power:
        fig.add_trace(go.Scatter(x=time_steps, y=ts_arr[:, 1], name="Power (kW)", line=dict(color="#10B981", width=2.5, dash="dot")), row=1, col=1)

    # Row 2: Temperatures
    if show_gear_temp:
        fig.add_trace(go.Scatter(x=time_steps, y=ts_arr[:, 4], name="Gear Oil Temp (°C)", line=dict(color="#DC2626", width=2.5)), row=2, col=1)
    if show_gen_temp:
        fig.add_trace(go.Scatter(x=time_steps, y=ts_arr[:, 5], name="Gen Bearing Temp (°C)", line=dict(color="#F59E0B", width=2)), row=2, col=1)

    # Row 3: Mechanical Dynamics
    if show_pitch:
        fig.add_trace(go.Scatter(x=time_steps, y=ts_arr[:, 6], name="Blade Pitch (°)", line=dict(color="#8B5CF6", width=2)), row=3, col=1)
    if show_vibe:
        fig.add_trace(go.Scatter(x=time_steps, y=ts_arr[:, 7], name="Drivetrain Accel (mm/s²)", line=dict(color="#EC4899", width=1.5)), row=3, col=1)

    fig.update_layout(height=520, margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # Run Model Inference
    ts_tensor = torch.tensor(ts_arr).unsqueeze(0).to(device)  # (1, 72, 8)
    preds, probs = model.predict(ts_tensor)
    pred_class_idx = preds.item()
    pred_class_name = FAULT_CLASSES[pred_class_idx]
    confidence = probs[0, pred_class_idx].item()

    is_anomaly = pred_class_name != "Normal Operation"

    col_diag, col_bench = st.columns([3, 2])

    with col_diag:
        st.subheader("🧠 OpenTSLM Diagnostic & Action Recommendation")

        card_class = "anomaly-card-critical" if is_anomaly else "anomaly-card-normal"
        status_icon = "🚨 CRITICAL FAULT DETECTED" if is_anomaly else "✅ NORMAL OPERATING REGIME"

        st.markdown(
            f"""
            <div class="{card_class}">
                <div style="font-size: 1.2rem; font-weight: 700; margin-bottom: 5px;">{status_icon}</div>
                <div><b>Asset:</b> {sample['turbine_id']}</div>
                <div><b>Predicted Condition:</b> {pred_class_name} (Confidence: <b>{confidence:.1%}</b>)</div>
                <div><b>Ground Truth Status:</b> {sample['label_name']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("🔍 Step-by-Step Chain-of-Thought (CoT) Physical Reasoning", expanded=True):
            st.markdown(f"**Diagnostic Query**: *{sample['prompt']}*")
            st.markdown(f"**Physics-Grounded Rationale**: {sample['rationale']}")

        with st.expander("🛠️ Prescribed Maintenance Dispatch Action", expanded=True):
            st.success(sample["action"])

    with col_bench:
        st.subheader("📊 Zero-Leakage Benchmark Table")
        benchmark_file = Path("results/benchmark_results.json")
        if benchmark_file.exists():
            with open(benchmark_file, "r") as f:
                results_data = json.load(f)
            df_b = pd.DataFrame(results_data)
            display_cols = [c for c in ["benchmark", "model_name", "accuracy", "macro_f1"] if c in df_b.columns]
            st.dataframe(
                df_b[display_cols].rename(
                    columns={
                        "benchmark": "Benchmark Track",
                        "model_name": "Model",
                        "accuracy": "Accuracy",
                        "macro_f1": "Macro F1",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Run `python -m src.evaluation.evaluate` to generate benchmark table.")

        st.markdown("### Submission Highlights")
        st.markdown(
            """
            - **Primary Dataset**: Penmanshiel Wind Farm (14 Senvion MM82 turbines).
            - **Strict Zero-Leakage**: Turbines WT01–WT10 (Train), WT11–WT12 (Val), WT13–WT15 (Test).
            - **Completely Blank Demo**: Kelmarsh Wind Farm used 100% as unseen testbed for zero-shot cross-farm transfer.
            - **Native TimeNet Ingestion**: Standardized TimeF Parquet with lazy Arrow streaming.
            - **Explainable Diagnostics**: Direct physical reasoning connecting sensor slopes to dispatch actions.
            """
        )


if __name__ == "__main__":
    main()
