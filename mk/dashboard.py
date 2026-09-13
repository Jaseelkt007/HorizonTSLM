"""Wind Turbine SCADA & Diagnostic Visualizer.

Interactive Streamlit application to inspect 8-channel SCADA telemetry
across Penmanshiel and Kelmarsh wind farms and benchmark neural time-series
models against verified ground truth.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Locate repository root and mk subdirectory
MK_DIR = Path(__file__).resolve().parent
_curr = MK_DIR
while not (_curr / "pyproject.toml").exists() and _curr.parent != _curr:
    _curr = _curr.parent
REPO_ROOT = _curr

for p in [MK_DIR, REPO_ROOT]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from mk.src.data.schemas import (
        COARSE_FAULT_TO_SUBSYSTEM,
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        KELMARSH_DATASET_ID,
        PENMANSHIEL_DATASET_ID,
        SELECTED_SIGNALS,
        SIGNAL_NAMES,
        SUBSYSTEM_CLASSES,
        SUBSYSTEM_TO_COARSE_FAULT,
        WINDOW_STEPS,
        WINDOW_STEPS_12H,
    )
    from mk.src.data.preprocessor import check_telemetry_anomalies, classify_window_events
    from mk.src.models.architecture import (
        OpenTSLMForTurbineDiagnosis,
        OpenTSLMSoftPromptForTurbineDiagnosis,
    )
except ImportError:
    from src.data.schemas import (
        COARSE_FAULT_TO_SUBSYSTEM,
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        KELMARSH_DATASET_ID,
        PENMANSHIEL_DATASET_ID,
        SELECTED_SIGNALS,
        SIGNAL_NAMES,
        SUBSYSTEM_CLASSES,
        SUBSYSTEM_TO_COARSE_FAULT,
        WINDOW_STEPS,
        WINDOW_STEPS_12H,
    )
    from src.data.preprocessor import check_telemetry_anomalies, classify_window_events
    from src.models.architecture import (
        OpenTSLMForTurbineDiagnosis,
        OpenTSLMSoftPromptForTurbineDiagnosis,
    )

# Visualizer styling constants
SUBSYSTEM_ICONS: dict[str, str] = {
    "gearbox_lubrication": "🔥",
    "generator_cooling": "🌡️",
    "generator_bearing": "⚙️",
    "pitch_system": "📐",
    "brake_hydraulics": "🛑",
    "converter_grid": "⚡",
    "yaw_cable": "🔄",
    "structural_overspeed": "🌪️",
    "sensor_comms": "📡",
    "environmental_stop": "🍃",
    "curtailment_external": "📉",
    "manual_safety": "🚨",
    "normal_operation": "✅",
}

SUBSYSTEM_COLORS: dict[str, str] = {
    "gearbox_lubrication": "#EF4444",
    "generator_cooling": "#F97316",
    "generator_bearing": "#F59E0B",
    "pitch_system": "#8B5CF6",
    "brake_hydraulics": "#DC2626",
    "converter_grid": "#06B6D4",
    "yaw_cable": "#6366F1",
    "structural_overspeed": "#D946EF",
    "sensor_comms": "#64748B",
    "environmental_stop": "#3B82F6",
    "curtailment_external": "#0284C7",
    "manual_safety": "#E11D48",
    "normal_operation": "#10B981",
}

SIGNAL_ORDER = [
    "wind_speed",
    "power",
    "rotor_speed",
    "generator_rpm",
    "gear_oil_temp",
    "gen_bearing_temp",
    "pitch_angle_a",
    "pitch_angle_b",
    "pitch_angle_c",
    "drivetrain_accel",
    "ambient_temp",
]


# =====================================================================
# DATA LOADING & CACHING
# =====================================================================

@st.cache_data(show_spinner="Loading wind farm metadata...")
def load_static_metadata(farm: str = "penmanshiel") -> pd.DataFrame:
    """Load turbine static geographic and technical specifications."""
    if farm.lower() == "penmanshiel":
        static_path = REPO_ROOT / "data" / "penmanshiel" / "Penmanshiel_WT_static.csv"
    else:
        static_path = REPO_ROOT / "data" / "kelmarsh" / "Kelmarsh_WT_static.csv"
    if static_path.exists():
        return pd.read_csv(static_path)
    return pd.DataFrame()


@st.cache_data(show_spinner="Loading and caching SCADA telemetry...")
def load_timenet_dataset(
    dataset_id: str = "energy/penmanshiel-wind-scada",
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Load records and 8-channel signals from TimeNet local registry."""
    from timenet.client import TimeNet
    from timenet.registry.factory import default_registry_path

    client = TimeNet(registry=default_registry_path())
    try:
        dataset = client.load(dataset_id)
    except Exception:  # noqa: BLE001
        fallback_id = (
            "energy/kelmarsh-wind-scada"
            if dataset_id != "energy/kelmarsh-wind-scada"
            else "energy/penmanshiel-wind-scada"
        )
        dataset = client.load(fallback_id)

    records_list = []
    telemetry_dict = {}

    is_penmanshiel = "penmanshiel" in dataset_id.lower()
    farm_name = "Penmanshiel" if is_penmanshiel else "Kelmarsh"
    turbine_model = (
        "Senvion MM82 (2.05 MW)" if is_penmanshiel else "Senvion MM92 (2.05 MW)"
    )

    for r in dataset.records:
        rec_id = r.record_id
        rec_data: dict[str, Any] = {
            "record_id": rec_id,
            "start_time_us": r.start_time,
            "start_time": pd.to_datetime(r.start_time, unit="us", utc=True),
            "wind_farm": farm_name,
            "turbine_model": turbine_model,
        }
        for a in r.annotations:
            if a.key == "turbine_id":
                rec_data["turbine_id"] = a.value
            elif a.key == "fault_class":
                rec_data["fault_class"] = a.value
            elif a.key == "wind_farm":
                rec_data["wind_farm"] = a.value

        if "turbine_id" not in rec_data:
            rec_data["turbine_id"] = f"{farm_name} WT"

        tasks = [t for t in dataset.tasks if rec_id in t.record_ids]
        for t in tasks:
            if type(t).__name__ == "AnswerTask":
                rec_data["prompt"] = getattr(t, "prompt", "")
                rec_data["target"] = getattr(t, "target", "")
                rec_data["rationale"] = getattr(t, "rationale", "")

        sig_map = {}
        for ts in r.time_series:
            sig_map[ts.signal] = ts.to_numpy()

        n_steps = len(next(iter(sig_map.values()))) if sig_map else WINDOW_STEPS
        rec_data["end_time"] = rec_data["start_time"] + pd.Timedelta(
            minutes=10 * n_steps
        )

        timestamps = pd.date_range(
            start=rec_data["start_time"],
            periods=n_steps,
            freq="10min",
            tz="UTC",
        )
        win_df = pd.DataFrame(sig_map, index=timestamps)
        win_df.index.name = "timestamp"

        telemetry_dict[rec_id] = win_df
        records_list.append(rec_data)

    df_records = pd.DataFrame(records_list)
    return df_records, telemetry_dict


@st.cache_data(show_spinner="Loading both wind farms (Penmanshiel & Kelmarsh)...")
def load_all_wind_farms() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Loads and combines all records from both Penmanshiel and Kelmarsh."""
    df_pen, tel_pen = load_timenet_dataset(PENMANSHIEL_DATASET_ID)
    df_kel, tel_kel = load_timenet_dataset(KELMARSH_DATASET_ID)
    df_combined = pd.concat([df_pen, df_kel], ignore_index=True)
    tel_combined = {**tel_pen, **tel_kel}
    return df_combined, tel_combined


# =====================================================================
# INFERENCE & MODEL WRAPPER
# =====================================================================

class ModelInferenceResult:
    """Encapsulates discrete neural predictions and generative CoT outputs."""

    def __init__(
        self,
        pred_idx: int,
        pred_name: str,
        probs: np.ndarray,
        model_type: str = "encoder",
        classes: list[str] | None = None,
        generated_text: str | None = None,
        parsed_subsystem: str | None = None,
        parsed_triage: str = "normal",
        parsed_answer: str = "",
    ):
        self.pred_idx = pred_idx
        self.pred_name = pred_name
        self.probs = probs
        self.confidence = float(probs[pred_idx]) if len(probs) > pred_idx else 0.0
        self.model_type = model_type
        self.classes = classes or FAULT_CLASSES
        self.generated_text = generated_text or ""
        # The primary inferred subsystem is always grounded in the neural classifier head
        self.parsed_subsystem = parsed_subsystem or pred_name
        self.parsed_triage = parsed_triage
        self.parsed_answer = parsed_answer
        self.coarse_fault = (
            SUBSYSTEM_TO_COARSE_FAULT.get(pred_name, "Normal Operation")
            if model_type == "softprompt"
            else pred_name
        )

    def __iter__(self):
        yield self.pred_idx
        yield self.pred_name
        yield self.probs

    def __getitem__(self, idx: int):
        return [self.pred_idx, self.pred_name, self.probs][idx]


@st.cache_resource(show_spinner="Loading trained OpenTSLM model checkpoint...")
def load_trained_model(preferred_type: str = "softprompt"):
    """Loads trained OpenTSLM model weights for real-time inference."""
    try:
        import torch

        device = torch.device("cpu")

        if preferred_type == "softprompt":
            sp_path = REPO_ROOT / "mk" / "checkpoints" / "opentslm_softprompt_best.pt"
            if not sp_path.exists():
                sp_path = REPO_ROOT / "checkpoints" / "opentslm_softprompt_best.pt"

            if sp_path.exists():
                from transformers import GPT2Tokenizer

                tok = GPT2Tokenizer.from_pretrained("openai-community/gpt2")
                tok.pad_token = tok.eos_token

                model = OpenTSLMSoftPromptForTurbineDiagnosis(
                    in_channels=11,
                    patch_size=4,
                    d_encoder=256,
                    d_llm=768,
                    num_classes=len(SUBSYSTEM_CLASSES),
                    llm_model_name="openai-community/gpt2",
                )
                checkpoint = torch.load(
                    sp_path, map_location="cpu", weights_only=False
                )
                model.load_state_dict(checkpoint["model_state_dict"])
                model.to(device)
                model.eval()

                meta = {
                    "type": "softprompt",
                    "epoch": checkpoint.get("epoch", 20),
                    "val_f1": checkpoint.get("val_f1", 0.0),
                    "val_loss": checkpoint.get("val_loss", 0.0),
                    "device": str(device),
                    "tokenizer": tok,
                    "classes": SUBSYSTEM_CLASSES,
                }
                return model, meta

        # Default / encoder checkpoint fallback
        checkpoint_path = REPO_ROOT / "mk" / "checkpoints" / "opentslm_best.pt"
        if not checkpoint_path.exists():
            checkpoint_path = REPO_ROOT / "checkpoints" / "opentslm_best.pt"
        if not checkpoint_path.exists():
            return None, "Checkpoint not found."

        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
        model = OpenTSLMForTurbineDiagnosis(
            in_channels=11, patch_size=4, d_encoder=256, d_llm=512
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.to(device)
        model.eval()

        meta = {
            "type": "encoder",
            "epoch": checkpoint.get("epoch", 1),
            "val_f1": checkpoint.get("val_f1", 0.0),
            "device": str(device),
            "classes": FAULT_CLASSES,
        }
        return model, meta
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def run_model_inference(
    model, telemetry_df: pd.DataFrame, meta_or_device: Any = "cpu"
) -> ModelInferenceResult:
    """Runs forward pass on telemetry window and returns ModelInferenceResult."""
    import torch

    if isinstance(meta_or_device, dict):
        device_str = meta_or_device.get("device", "cpu")
        meta = meta_or_device
    else:
        device_str = str(meta_or_device)
        meta = {"device": device_str, "type": "encoder"}

    device = torch.device(device_str)
    raw_mat = telemetry_df[SIGNAL_ORDER].values.astype(np.float32)
    tensor_x = torch.from_numpy(raw_mat).unsqueeze(0).to(device)

    is_softprompt = (
        isinstance(model, OpenTSLMSoftPromptForTurbineDiagnosis)
        or meta.get("type") == "softprompt"
    )

    if is_softprompt:
        tokenizer = meta.get("tokenizer")
        if tokenizer is None:
            from transformers import GPT2Tokenizer

            tokenizer = GPT2Tokenizer.from_pretrained("openai-community/gpt2")
            tokenizer.pad_token = tokenizer.eos_token

        classes = meta.get("classes", SUBSYSTEM_CLASSES)
        with torch.no_grad():
            # 1. Calibrated time-series classification head
            outputs = model(tensor_x)
            probs_np = torch.softmax(outputs["cls_logits"], dim=-1)[0].cpu().numpy()

            # 2. Autoregressive CoT diagnostic generation
            diag = model.generate_diagnosis(
                time_series=tensor_x,
                tokenizer=tokenizer,
                max_new_tokens=140,
                temperature=0.2,
            )

            pred_idx = int(diag.get("cls_pred_idx", np.argmax(probs_np)))
            pred_name = classes[pred_idx]
            parsed_sub = diag.get("parsed_subsystem", pred_name)
            parsed_triage = diag.get("parsed_triage", "normal" if pred_idx == 0 else "fault")

        return ModelInferenceResult(
            pred_idx=pred_idx,
            pred_name=pred_name,
            probs=probs_np,
            model_type="softprompt",
            classes=classes,
            generated_text=diag.get("generated_text", ""),
            parsed_subsystem=parsed_sub,
            parsed_triage=parsed_triage,
            parsed_answer=diag.get("parsed_answer", ""),
        )
    else:
        with torch.no_grad():
            preds, probs = model.predict(tensor_x)

        pred_idx = preds.item()
        pred_name = IDX_TO_FAULT_CLASS[pred_idx]
        probs_np = probs.cpu().numpy()[0]
        return ModelInferenceResult(
            pred_idx=pred_idx,
            pred_name=pred_name,
            probs=probs_np,
            model_type="encoder",
            classes=FAULT_CLASSES,
            parsed_subsystem=pred_name,
            parsed_triage="normal" if pred_name == "Normal Operation" else "fault",
        )


# =====================================================================
# AERODYNAMICS & SUPERVISORY REPORT FORMATTERS
# =====================================================================

def compute_theoretical_power(
    wind_speeds: np.ndarray, model: str = "MM92"
) -> np.ndarray:
    """Compute theoretical Senvion MM82/MM92 power curve (rated 2050 kW)."""
    cut_in = 3.0
    rated_speed = 12.5 if "MM92" in model else 13.0
    cut_out = 25.0
    rated_power = 2050.0

    p = np.zeros_like(wind_speeds, dtype=float)
    valid_mask = (wind_speeds >= cut_in) & (wind_speeds < rated_speed)
    p[valid_mask] = (
        rated_power * ((wind_speeds[valid_mask] - cut_in) / (rated_speed - cut_in)) ** 3
    )
    p[(wind_speeds >= rated_speed) & (wind_speeds <= cut_out)] = rated_power
    p[wind_speeds > cut_out] = 0.0
    return np.clip(p, 0.0, rated_power)


def format_tslm_explanation(
    rec_row: pd.Series, telemetry_df: pd.DataFrame
) -> dict[str, str]:
    """Formats standardized 5-part TSLM report (FINDING/EVIDENCE/CAUSE/IMPACT/ACTION)."""
    mean_wind = float(telemetry_df["wind_speed"].mean())
    mean_power = float(telemetry_df["power"].mean())
    max_power = float(telemetry_df["power"].max())
    mean_rotor = float(telemetry_df["rotor_speed"].mean())
    mean_gen_rpm = float(telemetry_df["generator_rpm"].mean())
    start_oil = float(telemetry_df["gear_oil_temp"].iloc[0])
    end_oil = float(telemetry_df["gear_oil_temp"].iloc[-1])
    oil_delta = end_oil - start_oil
    max_bearing = float(telemetry_df["gen_bearing_temp"].max())
    if "pitch_angle_a" in telemetry_df:
        mean_pitch = float(telemetry_df[["pitch_angle_a", "pitch_angle_b", "pitch_angle_c"]].mean().mean())
    elif "pitch_angle" in telemetry_df:
        mean_pitch = float(telemetry_df["pitch_angle"].mean())
    else:
        mean_pitch = 0.0
    max_vibe = float(telemetry_df["drivetrain_accel"].max())

    fc = rec_row["fault_class"]
    turbine = rec_row["turbine_id"]
    rationale = rec_row.get("rationale", "")
    target = rec_row.get("target", "")

    if fc == "Gearbox Overheating":
        finding = f"Abnormal thermal excursion detected in mechanical drive train on {turbine}."
        evidence = f"Wind speed averaged {mean_wind:.1f} m/s with power of {mean_power:.1f} kW. Gear oil temp rose from {start_oil:.1f}°C to {end_oil:.1f}°C (+{oil_delta:.1f}°C rise)."
        cause = "Degraded heat dissipation in gearbox lubrication loop, restricted radiator airflow, or oil pump cavitation."
        impact = "Elevated risk of gear tooth micro-pitting and bearing raceway degradation."
        action = "Curtail active power to 50% immediately. Inspect oil radiator, pump pressure, and sample lubricant."
    elif fc == "Generator Bearing Anomaly":
        finding = f"High localized thermal friction identified on generator drive-end bearing of {turbine}."
        evidence = f"Generator speed averaged {mean_gen_rpm:.0f} RPM with power of {mean_power:.1f} kW. Drive-end bearing temperature reached peak {max_bearing:.1f}°C."
        cause = "Bearing lubricant degradation, grease starvation, or early raceway spalling."
        impact = "Danger of catastrophic generator bearing seizure if temperature exceeds 85°C."
        action = "Schedule urgent off-peak vibration spectroscopy and high-frequency grease replenishment."
    elif fc == "Pitch / Aerodynamic Fault":
        finding = f"Aerodynamic rotor imbalance and asymmetric blade pitch dynamics on {turbine}."
        evidence = f"Wind speed averaged {mean_wind:.1f} m/s with oscillating blade pitch (mean: {mean_pitch:.1f}°) and vibration peaks at {max_vibe:.1f} mm/s²."
        cause = "Pitch actuator servo error, proportional valve stickiness, or hydraulic cylinder seal leakage."
        impact = "Severe cyclic mechanical fatigue on main shaft and low-speed gearbox stage."
        action = "Initiate automated blade pitch recalibration sequence. Inspect hydraulic pitch manifold."
    elif fc == "Turbine Trip / Forced Outage":
        finding = f"Unscheduled emergency forced outage and rapid safety trip occurred on {turbine}."
        evidence = f"Active power plunged abruptly from {max_power:.1f} kW to 0.0 kW within a single 10-min step. Rotor speed decelerated from {mean_rotor:.1f} RPM to idle, while blade pitch feathered to 90°."
        cause = "Hard safety chain trip, grid circuit breaker opening, or emergency stop button actuation."
        impact = f"Complete loss of power production (~{max_power * 12:.0f} potential kWh during 12h window)."
        action = "Examine SCADA safety chain relay logs and 24V loop continuity. Confirm grid synchronization voltage."
    else:  # Normal Operation
        finding = f"Stable, healthy operating conditions observed across all subsystems on {turbine}."
        evidence = f"Wind speed averaged {mean_wind:.1f} m/s yielding steady power output of {mean_power:.1f} kW. Temperatures and vibrations remained well within nominal envelopes."
        cause = "Normal turbine operation within certified IEC 61400-1 design envelope."
        impact = "Zero lost production. Asset operating at optimal capacity factor."
        action = "No corrective maintenance required. Maintain standard supervisory telemetry monitoring."

    if rationale and len(rationale) > 20:
        evidence = rationale
    if target and "Action:" in target:
        action = target.split("Action:")[1].strip()

    return {
        "finding": finding,
        "evidence": evidence,
        "cause": cause,
        "impact": impact,
        "action": action,
        "answer": fc,
    }


# =====================================================================
# STREAMLIT UI APPLICATION
# =====================================================================

def main():
    try:
        st.set_page_config(
            page_title="Wind Farm SCADA Visualizer",
            page_icon="⚡",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except (AttributeError, RuntimeError):
        pass

    # Clean styling
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        .stMetric { background-color: var(--secondary-background-color); padding: 10px 14px; border-radius: 8px; }
        .match-badge { font-weight: 700; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
        .match-ok { background: #10B98122; color: #10B981; border: 1px solid #10B981; }
        .match-fail { background: #EF444422; color: #EF4444; border: 1px solid #EF4444; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ------------------ SIDEBAR CONTROLS ------------------
    st.sidebar.title("⚡ SCADA Visualizer")
    st.sidebar.caption("Unified Fleet Diagnostics & Neural Benchmark")

    df_all, telemetry_data = load_all_wind_farms()

    # Model checkpoint loading
    model_type_choice = st.sidebar.radio(
        "Active Model",
        ["softprompt", "encoder"],
        format_func=lambda x: "OpenTSLM-SoftPrompt (LoRA GPT-2)" if x == "softprompt" else "OpenTSLM Encoder (5-Class)",
    )
    model, model_meta = load_trained_model(preferred_type=model_type_choice)
    if isinstance(model_meta, dict):
        st.sidebar.success(
            f"Loaded: Epoch {model_meta.get('epoch', 1)} (Val F1: {model_meta.get('val_f1', 0.0):.3f})"
        )
    else:
        st.sidebar.warning(f"Model unavailable: {model_meta}")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Asset & Timeframe Filter")

    # Farm filter
    farm_filter = st.sidebar.selectbox("Wind Farm", ["All", "Penmanshiel", "Kelmarsh"])
    filtered_df = df_all if farm_filter == "All" else df_all[df_all["wind_farm"] == farm_filter]

    # Fault class filter
    classes_avail = ["All"] + sorted(filtered_df["fault_class"].unique().tolist())
    fault_filter = st.sidebar.selectbox("Fault Category", classes_avail)
    if fault_filter != "All":
        filtered_df = filtered_df[filtered_df["fault_class"] == fault_filter]

    # Turbine filter
    turbines_avail = ["All"] + sorted(filtered_df["turbine_id"].unique().tolist())
    turbine_filter = st.sidebar.selectbox("Turbine Asset", turbines_avail)
    if turbine_filter != "All":
        filtered_df = filtered_df[filtered_df["turbine_id"] == turbine_filter]

    if filtered_df.empty:
        st.warning("No records match the active filter criteria.")
        return

    # Record selector
    record_options = filtered_df["record_id"].tolist()
    record_format = {
        r: f"{r} | {filtered_df[filtered_df['record_id'] == r]['turbine_id'].iloc[0]} | {filtered_df[filtered_df['record_id'] == r]['fault_class'].iloc[0]}"
        for r in record_options
    }
    selected_rec_id = st.sidebar.selectbox(
        "Monitored Record ID",
        record_options,
        format_func=lambda r: record_format.get(r, r),
    )

    rec_row = df_all[df_all["record_id"] == selected_rec_id].iloc[0]
    cur_telemetry = telemetry_data[selected_rec_id]

    # ------------------ GROUND TRUTH CALCULATION ------------------
    raw_signals = cur_telemetry[SIGNAL_ORDER].values
    gt_fault_class = str(rec_row["fault_class"])

    # Directly map canonical fault class from TimeNet record annotations to subsystem and triage
    if gt_fault_class in COARSE_FAULT_TO_SUBSYSTEM:
        gt_subsystem = COARSE_FAULT_TO_SUBSYSTEM[gt_fault_class]
    elif gt_fault_class in SUBSYSTEM_CLASSES:
        gt_subsystem = gt_fault_class
    else:
        gt_subsystem = "normal_operation"

    gt_triage = "normal" if gt_subsystem == "normal_operation" else "fault"

    telemetry_flags = check_telemetry_anomalies(raw_signals)
    active_flags = [
        k.replace("_", " ").title()
        for k, v in telemetry_flags.items()
        if isinstance(v, bool) and v is True
    ]

    # ------------------ MODEL INFERENCE ------------------
    model_inference = None
    if model is not None and isinstance(model_meta, dict):
        model_inference = run_model_inference(
            model=model,
            telemetry_df=cur_telemetry,
            meta_or_device=model_meta,
        )

    # ------------------ HEADER DASHBOARD ------------------
    st.title("⚡ Wind Turbine SCADA Diagnostic Visualizer")
    st.caption(
        f"**Asset:** `{rec_row['turbine_id']}` ({rec_row['wind_farm']} Wind Farm, {rec_row['turbine_model']}) &nbsp;|&nbsp; "
        f"**Window ID:** `{selected_rec_id}` &nbsp;|&nbsp; "
        f"**Timespan:** `{rec_row['start_time'].strftime('%Y-%m-%d %H:%M')}` to `{rec_row['end_time'].strftime('%Y-%m-%d %H:%M')} UTC` (12 Hours)"
    )

    # Top KPI summary bar
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Wind Speed (Mean)", f"{cur_telemetry['wind_speed'].mean():.1f} m/s", f"Max {cur_telemetry['wind_speed'].max():.1f} m/s")
    with kpi2:
        st.metric("Active Power (Mean)", f"{cur_telemetry['power'].mean():.1f} kW", f"Peak {cur_telemetry['power'].max():.1f} kW")
    with kpi3:
        st.metric("Gearbox Oil Temp", f"{cur_telemetry['gear_oil_temp'].iloc[-1]:.1f} °C", f"Δ {cur_telemetry['gear_oil_temp'].iloc[-1] - cur_telemetry['gear_oil_temp'].iloc[0]:+.1f} °C")
    with kpi4:
        st.metric("Generator Bearing Temp", f"{cur_telemetry['gen_bearing_temp'].max():.1f} °C", f"Max vibe: {cur_telemetry['drivetrain_accel'].max():.1f} mm/s²")

    st.markdown("---")

    # ------------------ STAGE 1: BENCHMARK COMPARISON ------------------
    st.subheader("🎯 Ground Truth vs Neural Model Benchmark")

    col_gt, col_pred = st.columns(2)

    with col_gt:
        st.markdown("##### 🏷️ Verified Historical Ground Truth")
        st.caption("Derived from verified SCADA fault log records and domain physics:")

        gt_sub_icon = SUBSYSTEM_ICONS.get(gt_subsystem, "⚙️")
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.metric("Target Subsystem", f"{gt_sub_icon} {gt_subsystem}")
        with sub_c2:
            st.metric("Target Triage", gt_triage.upper())

        st.markdown(f"**Operator Fault Category**: `{gt_fault_class}`")
        if rec_row.get("rationale"):
            st.markdown(f"**Alarm Log / Narrative**: *\"{rec_row['rationale']}\"*")

        if active_flags:
            flags_str = ", ".join(f"`{f}`" for f in active_flags)
            st.markdown(f"**Active Physical Excursions**: {flags_str}")
        else:
            st.markdown("**Active Physical Excursions**: *Nominal physical envelope (no sensor excursions)*")

    with col_pred:
        st.markdown("##### 🤖 Live Neural Network Inference")
        if model_inference is not None:
            pred_subsystem = model_inference.pred_name
            pred_triage = model_inference.parsed_triage
            coarse_pred = model_inference.coarse_fault

            # Strict zero-fudge comparison
            sub_match = pred_subsystem.strip().lower() == gt_subsystem.strip().lower()
            tri_match = pred_triage.strip().lower() == gt_triage.strip().lower()
            coarse_match = coarse_pred.strip().lower() == gt_fault_class.strip().lower()

            st.caption(f"Evaluated with **{model_inference.model_type.upper()}** on continuous SCADA telemetry:")

            p_c1, p_c2 = st.columns(2)
            with p_c1:
                st.metric(
                    "Inferred Subsystem",
                    f"{SUBSYSTEM_ICONS.get(pred_subsystem, '🤖')} {pred_subsystem}",
                    "MATCH" if sub_match else "MISMATCH",
                    delta_color="normal" if sub_match else "inverse",
                )
            with p_c2:
                st.metric(
                    "Inferred Triage",
                    pred_triage.upper(),
                    "CONCORDANT" if tri_match else "DIVERGENT",
                    delta_color="normal" if tri_match else "inverse",
                )

            st.markdown(
                f"**Mapped Operator Class**: `{coarse_pred}` &nbsp; "
                f"<span class='match-badge {'match-ok' if coarse_match else 'match-fail'}'>{'✅ MATCH' if coarse_match else '❌ MISMATCH'}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**Classifier Top-1 Confidence**: `{model_inference.confidence * 100:.1f}%`")

            # Softmax distribution bar chart
            prob_df = pd.DataFrame(
                {"Subsystem": model_inference.classes, "Probability": model_inference.probs}
            ).sort_values("Probability", ascending=True).tail(5)

            fig_bar = px.bar(
                prob_df,
                x="Probability",
                y="Subsystem",
                orientation="h",
                text=prob_df["Probability"].apply(lambda p: f"{p * 100:.1f}%"),
                color="Subsystem",
                color_discrete_map=SUBSYSTEM_COLORS,
            )
            fig_bar.update_layout(
                height=160,
                margin={"l": 10, "r": 10, "t": 5, "b": 5},
                xaxis={"range": [0, 1.05], "tickformat": ".0%"},
                showlegend=False,
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No model loaded.")

    # ------------------ STAGE 2: AUTOREGRESSIVE DIAGNOSTIC NARRATIVE ------------------
    if model_inference is not None and model_inference.generated_text:
        st.markdown("---")
        st.subheader("💬 Autoregressive Chain-of-Thought Diagnosis (Live LLM)")
        st.caption("Token-by-token narrative generated by LoRA GPT-2 conditioned on continuous telemetry soft prompt embeddings:")
        st.code(model_inference.generated_text, language="yaml")

    # 5-Part Supervisory Target Expander
    with st.expander("📋 View Deterministic Supervisory Target Report (Task T1 Standard)"):
        tslm_report = format_tslm_explanation(rec_row, cur_telemetry)
        t_c1, t_c2 = st.columns([1, 4])
        with t_c1:
            st.write("**1. FINDING**")
            st.write("**2. EVIDENCE**")
            st.write("**3. CAUSE**")
            st.write("**4. IMPACT**")
            st.write("**5. ACTION**")
        with t_c2:
            st.write(tslm_report["finding"])
            st.write(tslm_report["evidence"])
            st.write(tslm_report["cause"])
            st.write(tslm_report["impact"])
            st.write(tslm_report["action"])

    # ------------------ STAGE 3: SYNCHRONIZED SCADA TELEMETRY ------------------
    st.markdown("---")
    st.subheader("📈 Multi-Sensor SCADA Telemetry (8 Channels)")

    fig_telem = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=[
            "Active Power (kW) & Wind Speed (m/s)",
            "Rotor Speed (RPM) & Generator RPM",
            "Gearbox Oil & Generator Bearing Temperatures (°C)",
            "Blade Pitch Angle (°) & Drivetrain Acceleration (mm/s²)",
        ],
    )

    t_idx = cur_telemetry.index

    # Subplot 1: Power & Wind
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["power"], name="Power (kW)", line=dict(color="#3B82F6", width=2)), row=1, col=1)
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["wind_speed"], name="Wind Speed (m/s)", line=dict(color="#10B981", dash="dash")), row=1, col=1)

    # Subplot 2: Speeds
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["rotor_speed"], name="Rotor Speed (RPM)", line=dict(color="#8B5CF6")), row=2, col=1)
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["generator_rpm"], name="Generator RPM", line=dict(color="#06B6D4")), row=2, col=1)

    # Subplot 3: Temperatures
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["gear_oil_temp"], name="Gear Oil Temp (°C)", line=dict(color="#EF4444", width=2)), row=3, col=1)
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["gen_bearing_temp"], name="Gen Bearing Temp (°C)", line=dict(color="#F59E0B")), row=3, col=1)

    # Subplot 4: Pitch & Vibration
    if "pitch_angle_a" in cur_telemetry:
        fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["pitch_angle_a"], name="Blade A Pitch (°)", line=dict(color="#EC4899")), row=4, col=1)
        fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["pitch_angle_b"], name="Blade B Pitch (°)", line=dict(color="#A855F7", dash="dot")), row=4, col=1)
        fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["pitch_angle_c"], name="Blade C Pitch (°)", line=dict(color="#6366F1", dash="dash")), row=4, col=1)
    elif "pitch_angle" in cur_telemetry:
        fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["pitch_angle"], name="Pitch Angle (°)", line=dict(color="#EC4899")), row=4, col=1)
    fig_telem.add_trace(go.Scatter(x=t_idx, y=cur_telemetry["drivetrain_accel"], name="Vibration (mm/s²)", line=dict(color="#64748B")), row=4, col=1)

    fig_telem.update_layout(height=650, margin=dict(l=40, r=40, t=40, b=20), hovermode="x unified")
    st.plotly_chart(fig_telem, use_container_width=True)

    # ------------------ STAGE 4: EMPIRICAL POWER CURVE ------------------
    st.markdown("---")
    st.subheader("🌪️ Empirical Power Curve & Aerodynamic Envelope")

    p_col1, p_col2 = st.columns([3, 2])
    with p_col1:
        # Generate theoretical reference
        ws_ref = np.linspace(0.0, 25.0, 100)
        p_ref = compute_theoretical_power(ws_ref, model=rec_row["turbine_model"])

        pitch_series = cur_telemetry["pitch_angle_a"] if "pitch_angle_a" in cur_telemetry else cur_telemetry.get("pitch_angle", cur_telemetry["power"])

        fig_pc = go.Figure()
        fig_pc.add_trace(
            go.Scatter(
                x=ws_ref,
                y=p_ref,
                mode="lines",
                name="Theoretical Curve (Senvion 2.05MW)",
                line=dict(color="#64748B", dash="dash", width=2),
            )
        )
        fig_pc.add_trace(
            go.Scatter(
                x=cur_telemetry["wind_speed"],
                y=cur_telemetry["power"],
                mode="markers",
                name="Observed 10-Min Telemetry",
                marker=dict(
                    size=7,
                    color=pitch_series,
                    colorscale="Viridis",
                    colorbar=dict(title="Pitch (°)"),
                    showscale=True,
                ),
            )
        )
        fig_pc.update_layout(
            xaxis_title="Wind Speed (m/s)",
            yaxis_title="Active Power (kW)",
            height=380,
            margin=dict(l=40, r=40, t=20, b=20),
        )
        st.plotly_chart(fig_pc, use_container_width=True)

    with p_col2:
        st.markdown("**Window Statistical Telemetry Distribution**")
        channel_rows = [
            ("Hub Wind Speed (m/s)", "wind_speed", ".1f"),
            ("Active Power (kW)", "power", ".1f"),
            ("Rotor Speed (RPM)", "rotor_speed", ".1f"),
            ("Generator Speed (RPM)", "generator_rpm", ".0f"),
            ("Gear Oil Temp (°C)", "gear_oil_temp", ".1f"),
            ("Gen Bearing Temp (°C)", "gen_bearing_temp", ".1f"),
        ]
        if "pitch_angle_a" in cur_telemetry:
            channel_rows.extend([
                ("Blade A Pitch (°)", "pitch_angle_a", ".1f"),
                ("Blade B Pitch (°)", "pitch_angle_b", ".1f"),
                ("Blade C Pitch (°)", "pitch_angle_c", ".1f"),
            ])
        elif "pitch_angle" in cur_telemetry:
            channel_rows.append(("Pitch Angle (°)", "pitch_angle", ".1f"))

        channel_rows.append(("Drivetrain Vibration (mm/s²)", "drivetrain_accel", ".1f"))
        if "ambient_temp" in cur_telemetry:
            channel_rows.append(("Ambient Temp (°C)", "ambient_temp", ".1f"))

        stats_df = pd.DataFrame(
            {
                "SCADA Channel": [r[0] for r in channel_rows],
                "Mean": [f"{cur_telemetry[r[1]].mean():{r[2]}}" for r in channel_rows],
                "Min": [f"{cur_telemetry[r[1]].min():{r[2]}}" for r in channel_rows],
                "Max": [f"{cur_telemetry[r[1]].max():{r[2]}}" for r in channel_rows],
            }
        )
        st.dataframe(stats_df, hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
