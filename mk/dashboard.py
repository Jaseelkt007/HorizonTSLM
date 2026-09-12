"""Interactive Streamlit visualizer to inspect wind turbine SCADA telemetry across both plants and model diagnostic outputs."""

import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Dynamically locate repository root and mk subfolder
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
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        KELMARSH_DATASET_ID,
        PENMANSHIEL_DATASET_ID,
        SELECTED_SIGNALS,
        SIGNAL_NAMES,
        SUBSYSTEM_CLASSES,
        SUBSYSTEM_TO_COARSE_FAULT,
        TRIAGE_CLASSES,
        WINDOW_STEPS,
        WINDOW_STEPS_12H,
        WINDOW_STEPS_24H,
    )
    from mk.src.data.preprocessor import classify_window_events
    from mk.src.models.architecture import (
        OpenTSLMForTurbineDiagnosis,
        OpenTSLMSoftPromptForTurbineDiagnosis,
    )
except ImportError:
    from src.data.schemas import (
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        KELMARSH_DATASET_ID,
        PENMANSHIEL_DATASET_ID,
        SELECTED_SIGNALS,
        SIGNAL_NAMES,
        SUBSYSTEM_CLASSES,
        SUBSYSTEM_TO_COARSE_FAULT,
        TRIAGE_CLASSES,
        WINDOW_STEPS,
        WINDOW_STEPS_12H,
        WINDOW_STEPS_24H,
    )
    from src.data.preprocessor import classify_window_events
    from src.models.architecture import (
        OpenTSLMForTurbineDiagnosis,
        OpenTSLMSoftPromptForTurbineDiagnosis,
    )

# Diagnostic class styling
FAULT_COLOR_MAP = {
    "Normal Operation": "#10B981",  # Emerald green
    "Gearbox Overheating": "#EF4444",  # Crimson red
    "Generator Bearing Anomaly": "#F59E0B",  # Amber orange
    "Pitch / Aerodynamic Fault": "#8B5CF6",  # Purple
    "Turbine Trip / Forced Outage": "#EC4899",  # Pink
}

FAULT_ICONS = {
    "Normal Operation": "✅",
    "Gearbox Overheating": "🔥",
    "Generator Bearing Anomaly": "⚙️",
    "Pitch / Aerodynamic Fault": "🌪️",
    "Turbine Trip / Forced Outage": "🛑",
}

SUBSYSTEM_COLOR_MAP = {
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

SUBSYSTEM_ICONS = {
    "gearbox_lubrication": "⚙️",
    "generator_cooling": "❄️",
    "generator_bearing": "🔄",
    "pitch_system": "📐",
    "brake_hydraulics": "🛑",
    "converter_grid": "⚡",
    "yaw_cable": "🔀",
    "structural_overspeed": "🌪️",
    "sensor_comms": "📡",
    "environmental_stop": "🌬️",
    "curtailment_external": "📉",
    "manual_safety": "🚨",
    "normal_operation": "✅",
}

TRIAGE_COLOR_MAP = {
    "normal": "#10B981",
    "benign_stop": "#3B82F6",
    "fault": "#EF4444",
}

TRIAGE_ICONS = {
    "normal": "🟢",
    "benign_stop": "🔵",
    "fault": "🔴",
}

SIGNAL_META = {s.canonical_name: s for s in SELECTED_SIGNALS}


@st.cache_data(show_spinner="Loading wind farm static specifications...")
def load_static_metadata(farm: str = "penmanshiel") -> pd.DataFrame:
    """Load turbine static geographic and technical specifications."""
    if farm.lower() == "penmanshiel":
        static_path = REPO_ROOT / "data" / "penmanshiel" / "Penmanshiel_WT_static.csv"
    else:
        static_path = REPO_ROOT / "data" / "kelmarsh" / "Kelmarsh_WT_static.csv"
    if static_path.exists():
        df = pd.read_csv(static_path)
        return df
    return pd.DataFrame()


@st.cache_data(show_spinner="Loading and caching TimeNet SCADA telemetry...")
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

        # Ensure turbine_id fallback
        if "turbine_id" not in rec_data:
            rec_data["turbine_id"] = f"{farm_name} WT"

        # Extract tasks
        tasks = [t for t in dataset.tasks if rec_id in t.record_ids]
        for t in tasks:
            if type(t).__name__ == "AnswerTask":
                rec_data["prompt"] = getattr(t, "prompt", "")
                rec_data["target"] = getattr(t, "target", "")
                rec_data["rationale"] = getattr(t, "rationale", "")

        # Extract time series signals
        sig_map = {}
        for ts in r.time_series:
            sig_map[ts.signal] = ts.to_numpy()

        n_steps = len(next(iter(sig_map.values()))) if sig_map else WINDOW_STEPS
        rec_data["end_time"] = rec_data["start_time"] + pd.Timedelta(
            minutes=10 * n_steps
        )

        # Build individual window dataframe
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
    """Loads and combines all records from both Penmanshiel and Kelmarsh wind farms into a unified dataset."""
    df_pen, tel_pen = load_timenet_dataset(PENMANSHIEL_DATASET_ID)
    df_kel, tel_kel = load_timenet_dataset(KELMARSH_DATASET_ID)

    df_combined = pd.concat([df_pen, df_kel], ignore_index=True)
    tel_combined = {**tel_pen, **tel_kel}
    return df_combined, tel_combined


class ModelInferenceResult:
    """Encapsulates discrete predictions, continuous probabilities, and generative CoT outputs."""

    def __init__(
        self,
        pred_idx: int,
        pred_name: str,
        probs: np.ndarray,
        model_type: str = "encoder",
        classes: list[str] | None = None,
        generated_text: str | None = None,
        parsed_subsystem: str = "normal_operation",
        parsed_triage: str = "normal",
        parsed_answer: str = "",
    ):
        self.pred_idx = pred_idx
        self.pred_name = pred_name
        self.probs = probs
        self.model_type = model_type
        self.classes = classes or FAULT_CLASSES
        self.generated_text = generated_text
        self.parsed_subsystem = parsed_subsystem
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

    def __getitem__(self, idx):
        return [self.pred_idx, self.pred_name, self.probs][idx]


@st.cache_resource(show_spinner="Loading trained OpenTSLM model checkpoint...")
def load_trained_model(preferred_type: str = "softprompt"):
    """Loads the trained OpenTSLM model weights for real-time inference."""
    try:
        import torch

        # For Streamlit web interactive inference, CPU is fast (<80ms) and prevents Apple MPS command buffer race conditions
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
                    in_channels=8,
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

        # Default / encoder checkpoint
        checkpoint_path = REPO_ROOT / "mk" / "checkpoints" / "opentslm_best.pt"
        if not checkpoint_path.exists():
            checkpoint_path = REPO_ROOT / "checkpoints" / "opentslm_best.pt"
        if not checkpoint_path.exists():
            return None, "Checkpoint not found."

        checkpoint = torch.load(
            checkpoint_path, map_location="cpu", weights_only=False
        )
        model = OpenTSLMForTurbineDiagnosis(
            in_channels=8, patch_size=4, d_encoder=256, d_llm=512
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
    """Runs model forward pass on telemetry window and returns ModelInferenceResult."""
    import torch

    if isinstance(meta_or_device, dict):
        device_str = meta_or_device.get("device", "cpu")
        meta = meta_or_device
    else:
        device_str = str(meta_or_device)
        meta = {"device": device_str, "type": "encoder"}

    device = torch.device(device_str)
    sig_order = [
        "wind_speed",
        "power",
        "rotor_speed",
        "generator_rpm",
        "gear_oil_temp",
        "gen_bearing_temp",
        "pitch_angle",
        "drivetrain_accel",
    ]
    raw_mat = telemetry_df[sig_order].values.astype(np.float32)
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
            ts_embeds = model.get_time_series_embeddings(tensor_x)
            pooled = ts_embeds.mean(dim=1)
            logits = model.classifier(pooled)
            probs_np = torch.softmax(logits, dim=-1)[0].cpu().numpy()
            pred_idx = int(np.argmax(probs_np))
            pred_name = classes[pred_idx]

            # Autoregressive generation conditioned on soft prompt
            diag = model.generate_diagnosis(
                time_series=tensor_x,
                tokenizer=tokenizer,
                max_new_tokens=140,
                temperature=0.2,
            )

        return ModelInferenceResult(
            pred_idx=pred_idx,
            pred_name=pred_name,
            probs=probs_np,
            model_type="softprompt",
            classes=classes,
            generated_text=diag.get("generated_text", ""),
            parsed_subsystem=diag.get("parsed_subsystem", pred_name),
            parsed_triage=diag.get("parsed_triage", "normal"),
            parsed_answer=diag.get("parsed_answer", ""),
        )
    else:
        with torch.no_grad():
            preds, probs = model.predict(tensor_x)

        pred_idx = preds.item()
        pred_name = IDX_TO_FAULT_CLASS[pred_idx]
        probs_np = probs[0].cpu().numpy()
        return ModelInferenceResult(
            pred_idx=pred_idx,
            pred_name=pred_name,
            probs=probs_np,
            model_type="encoder",
            classes=FAULT_CLASSES,
            generated_text=None,
            parsed_subsystem=pred_name,
            parsed_triage="fault" if pred_name != "Normal Operation" else "normal",
            parsed_answer=pred_name,
        )


def format_tslm_explanation(
    rec_row: pd.Series, telemetry_df: pd.DataFrame
) -> dict[str, str]:
    """Formats the standardized 5-part TSLM diagnostic output (FINDING/EVIDENCE/CAUSE/IMPACT/ACTION)."""
    mean_wind = float(telemetry_df["wind_speed"].mean())
    mean_power = float(telemetry_df["power"].mean())
    max_power = float(telemetry_df["power"].max())
    mean_rotor = float(telemetry_df["rotor_speed"].mean())
    mean_gen_rpm = float(telemetry_df["generator_rpm"].mean())
    start_oil = float(telemetry_df["gear_oil_temp"].iloc[0])
    end_oil = float(telemetry_df["gear_oil_temp"].iloc[-1])
    oil_delta = end_oil - start_oil
    max_bearing = float(telemetry_df["gen_bearing_temp"].max())
    mean_pitch = float(telemetry_df["pitch_angle"].mean())
    max_vibe = float(telemetry_df["drivetrain_accel"].max())

    fc = rec_row["fault_class"]
    turbine = rec_row["turbine_id"]

    rationale = rec_row.get("rationale", "")
    target = rec_row.get("target", "")

    if fc == "Gearbox Overheating":
        finding = f"Abnormal thermal excursion detected in mechanical drive train on {turbine} under steady generation."
        evidence = f"Wind speed averaged {mean_wind:.1f} m/s with electrical power of {mean_power:.1f} kW. Gearbox oil temperature climbed from {start_oil:.1f}°C to {end_oil:.1f}°C (+{oil_delta:.1f}°C rise) despite steady electrical load, while bearing temperature reached {max_bearing:.1f}°C."
        cause = "Degraded heat dissipation in gearbox lubrication loop, restricted radiator cooling airflow, or oil pump cavitation."
        lost_kwh = max(0.0, (2050.0 - mean_power) * 0.5 * 12.0)
        impact = f"Elevated risk of accelerated gear tooth micro-pitting and bearing raceway degradation. Potential curtailment energy loss: ~{lost_kwh:.0f} kWh."
        action = "Curtail active power output to 50% rated capacity immediately. Dispatch maintenance crew to inspect oil radiator, verify pump pressure, and sample lubricant for metallic particulate contamination."
    elif fc == "Generator Bearing Anomaly":
        finding = f"High localized thermal friction anomaly identified on generator drive-end bearing of {turbine}."
        evidence = f"Turbine operated at average generator speed of {mean_gen_rpm:.0f} RPM with electrical output of {mean_power:.1f} kW. Drive-end generator bearing front temperature rose to an elevated peak of {max_bearing:.1f}°C under normal ambient conditions."
        cause = "Bearing lubricant degradation, grease starvation, or early-stage raceway spalling causing abnormal mechanical friction."
        impact = "Elevated danger of catastrophic generator bearing seizure and unplanned nacelle replacement if bearing temperature exceeds 85°C."
        action = "Schedule urgent off-peak vibration spectroscopy and high-frequency grease replenishment. Set automatic supervisory trip threshold at 85°C."
    elif fc == "Pitch / Aerodynamic Fault":
        finding = f"Aerodynamic rotor imbalance and asymmetric blade pitch dynamics observed on {turbine}."
        evidence = f"Wind speed averaged {mean_wind:.1f} m/s, but blade pitch angle exhibited rapid oscillations (mean: {mean_pitch:.1f}°) strongly coupled with drivetrain vibration shocks peaking at {max_vibe:.1f} mm/s²."
        cause = "Pitch actuator servo error, proportional valve stickiness, or hydraulic cylinder seal pressure leakage."
        impact = "Severe cyclic mechanical fatigue on main shaft and low-speed gearbox stage; potential aerodynamic overspeed risk."
        action = "Initiate automated blade pitch recalibration sequence. Inspect hydraulic pitch manifold, proportional valves, and accumulator pressure."
    elif fc == "Turbine Trip / Forced Outage":
        finding = f"Unscheduled emergency forced outage and rapid safety trip occurred on {turbine}."
        evidence = f"Active power plunged abruptly from {max_power:.1f} kW down to 0.0 kW within a single 10-minute timestep. Rotor speed decelerated from {mean_rotor:.1f} RPM down to idle (~0 RPM), while blade pitch immediately feathered to 90°."
        cause = "Hard safety chain trip, grid circuit breaker opening, or emergency stop button actuation."
        impact = f"Complete loss of power production (~{max_power * 12:.0f} potential kWh during 12-hour window). Turbine currently idle awaiting clearance."
        action = "Examine SCADA safety chain relay logs and 24V loop continuity. Confirm grid synchronization voltage and perform remote reset sequence."
    else:  # Normal Operation
        finding = f"Stable, healthy operating conditions observed across all mechanical, aerodynamic, and electrical subsystems on {turbine}."
        evidence = f"Wind speed averaged {mean_wind:.1f} m/s yielding steady power output of {mean_power:.1f} kW. Gearbox oil temp ({end_oil:.1f}°C) and bearing temp ({max_bearing:.1f}°C) remained well within nominal thresholds. Drivetrain vibration remained calm at {max_vibe:.1f} mm/s²."
        cause = "Normal turbine operation within certified IEC 61400-1 design envelope."
        impact = "Zero lost production. Asset operating at optimal capacity factor."
        action = "No corrective maintenance required. Maintain standard 10-minute SCADA supervisory telemetry monitoring."

    # Use exact dataset rationale and target when available
    if rationale and len(rationale) > 20:
        evidence = rationale
    if target and "Action:" in target:
        parts = target.split("Action:")
        action = parts[1].strip()

    return {
        "finding": finding,
        "evidence": evidence,
        "cause": cause,
        "impact": impact,
        "action": action,
        "answer": fc,
    }


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


def main():
    try:
        st.set_page_config(
            page_title="Wind Farm SCADA Visualizer | Penmanshiel & Kelmarsh",
            page_icon="⚡",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except (AttributeError, RuntimeError):
        pass

    # Custom styling
    st.markdown(
        """
        <style>
        .report-section {
            background-color: var(--secondary-background-color);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
            border-left: 4px solid #3B82F6;
        }
        .metric-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .report-label {
            font-weight: 700;
            font-size: 0.8rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 1.0rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ------------------ LOAD DATA & MODEL ------------------
    df_all_records, telemetry_dict = load_all_wind_farms()
    load_static_metadata("penmanshiel")
    load_static_metadata("kelmarsh")

    # ------------------ SIDEBAR CONTROLS ------------------
    st.sidebar.image("https://img.icons8.com/fluency/96/wind-turbine.png", width=56)
    st.sidebar.title("Fleet SCADA Visualizer")
    st.sidebar.caption("Penmanshiel & Kelmarsh Wind Farms | OpenTSLM")

    st.sidebar.markdown("---")
    st.sidebar.subheader("1. Wind Farm Selection")
    farm_filter = st.sidebar.radio(
        "Select Wind Farm Scope:",
        [
            "🌐 Both Wind Farms (20 Turbines)",
            "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Penmanshiel Wind Farm (14 Turbines)",
            "🇬🇧 Kelmarsh Wind Farm (6 Turbines)",
        ],
        index=0,
    )

    # Filter dataframe by farm
    if "Penmanshiel" in farm_filter and "Both" not in farm_filter:
        df_farm = df_all_records[df_all_records["wind_farm"] == "Penmanshiel"].copy()
    elif "Kelmarsh" in farm_filter and "Both" not in farm_filter:
        df_farm = df_all_records[df_all_records["wind_farm"] == "Kelmarsh"].copy()
    else:
        df_farm = df_all_records.copy()

    st.sidebar.markdown("---")
    st.sidebar.subheader("2. Turbine Selection")

    # Get available turbines
    all_turbines_in_scope = sorted(df_farm["turbine_id"].unique().tolist())
    turbine_options = ["All Turbines in Scope"] + all_turbines_in_scope

    selected_turbine_option = st.sidebar.selectbox(
        "Choose Turbine:",
        turbine_options,
        index=0,
        help="Select any of the 14 Penmanshiel or 6 Kelmarsh turbines",
    )

    # Filter by turbine
    if selected_turbine_option != "All Turbines in Scope":
        df_turbine_filtered = df_farm[
            df_farm["turbine_id"] == selected_turbine_option
        ].copy()
    else:
        df_turbine_filtered = df_farm.copy()

    st.sidebar.markdown("---")
    st.sidebar.subheader("3. Operational State Filter")
    fault_categories = ["All Categories"] + sorted(
        df_turbine_filtered["fault_class"].unique().tolist()
    )
    selected_category = st.sidebar.selectbox(
        "Fault / Event Class:", fault_categories, index=0
    )

    if selected_category != "All Categories":
        filtered_records = df_turbine_filtered[
            df_turbine_filtered["fault_class"] == selected_category
        ].copy()
    else:
        filtered_records = df_turbine_filtered.copy()

    if filtered_records.empty:
        st.sidebar.warning("No records match the selected filters.")
        st.warning(
            "No telemetry windows found for the selected turbine and category filters."
        )
        return

    st.sidebar.info(
        f"**{len(filtered_records)}** of **{len(df_all_records)}** windows match filters "
        f"({filtered_records['turbine_id'].nunique()} turbine(s))."
    )

    # ------------------ TIMEFRAME SELECTOR ------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("4. Timeframe / Window Selector")

    window_records = filtered_records.sort_values("start_time").to_dict("records")
    window_ids = [r["record_id"] for r in window_records]

    # Quick Navigation Buttons
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.sidebar.columns(5)
    curr_idx = st.session_state.get("nav_window_idx", 0)
    if curr_idx >= len(window_ids):
        curr_idx = 0

    with nav_col1:
        if st.button("⏮️", help="First window"):
            curr_idx = 0
            st.session_state["nav_window_idx"] = curr_idx
    with nav_col2:
        if st.button("◀️", help="Previous window"):
            curr_idx = max(0, curr_idx - 1)
            st.session_state["nav_window_idx"] = curr_idx
    with nav_col3:
        if st.button("🎲", help="Random window"):
            curr_idx = random.randint(0, len(window_ids) - 1)
            st.session_state["nav_window_idx"] = curr_idx
    with nav_col4:
        if st.button("▶️", help="Next window"):
            curr_idx = min(len(window_ids) - 1, curr_idx + 1)
            st.session_state["nav_window_idx"] = curr_idx
    with nav_col5:
        if st.button("⏭️", help="Last window"):
            curr_idx = len(window_ids) - 1
            st.session_state["nav_window_idx"] = curr_idx

    # Format window selector dropdown
    def format_window_label(rec_id: str) -> str:
        row = filtered_records[filtered_records["record_id"] == rec_id].iloc[0]
        start_str = row["start_time"].strftime("%Y-%m-%d %H:%M")
        fc_icon = FAULT_ICONS.get(row["fault_class"], "📌")
        return f"{rec_id} | {row['turbine_id']} | {start_str} | {fc_icon} {row['fault_class']}"

    selected_record_id = st.sidebar.selectbox(
        "Select Specific Timeframe:",
        window_ids,
        index=curr_idx,
        format_func=format_window_label,
    )
    st.session_state["nav_window_idx"] = window_ids.index(selected_record_id)

    # Signal visualization options
    st.sidebar.markdown("---")
    st.sidebar.subheader("5. Signal Options")
    unit_mode = st.sidebar.radio(
        "Telemetry Scaling:",
        [
            "Physical Engineering Units",
            "Normalized (Z-Score)",
            "Min-Max Normalized [0, 1]",
        ],
        index=0,
    )
    visible_signals = st.sidebar.multiselect(
        "Active Sensor Channels:",
        SIGNAL_NAMES,
        default=SIGNAL_NAMES,
        format_func=lambda s: f"{s} ({SIGNAL_META[s].unit})",
    )

    # ------------------ OPEN-TSLM INFERENCE ENGINE ------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("6. OpenTSLM Model Engine")
    model_choice = st.sidebar.selectbox(
        "Active Diagnostic Architecture:",
        [
            "OpenTSLM-SoftPrompt (LoRA GPT-2 + Subsystem Triage)",
            "OpenTSLM Encoder Baseline (5-Class)",
        ],
        index=0,
        help="Toggle between the generative OpenTSLM-SoftPrompt dual-head model (with autoregressive natural language explanation & 12-subsystem triage) and the 5-class encoder baseline.",
    )
    pref_type = "softprompt" if "SoftPrompt" in model_choice else "encoder"
    model, model_meta = load_trained_model(preferred_type=pref_type)

    if model is not None and isinstance(model_meta, dict):
        st.sidebar.success(
            f"Active: **{model_meta.get('type', 'encoder').upper()}** (Epoch {model_meta.get('epoch', 1)}, Val F1: {model_meta.get('val_f1', 0.0):.3f})"
        )
    else:
        st.sidebar.warning(f"Model checkpoint status: {model_meta}")

    # ------------------ CURRENT WINDOW DATA ------------------
    rec_row = filtered_records[
        filtered_records["record_id"] == selected_record_id
    ].iloc[0]
    cur_telemetry = telemetry_dict[selected_record_id]

    # Ground Truth Extraction via canonical rules and physical telemetry cross-validation
    sig_order = [
        "wind_speed",
        "power",
        "rotor_speed",
        "generator_rpm",
        "gear_oil_temp",
        "gen_bearing_temp",
        "pitch_angle",
        "drivetrain_accel",
    ]
    raw_signals = cur_telemetry[sig_order].values

    gt_events = []
    if rec_row.get("rationale"):
        gt_events.append(
            {
                "description": str(rec_row["rationale"]),
                "event_code": 0,
                "status_category": str(rec_row["fault_class"]),
            }
        )

    gt_res = classify_window_events(
        events_in_window=gt_events,
        signals_arr=raw_signals,
        mode="subsystem",
    )
    gt_subsystem = gt_res.subsystem
    gt_triage = gt_res.triage
    gt_severity = gt_res.severity
    gt_telemetry_flags = gt_res.telemetry_flags

    # Model inference (discrete + generative)
    model_inference = None
    model_pred_name = None
    model_probs = None
    model_confidence = 0.0
    if model is not None and isinstance(model_meta, dict):
        model_inference = run_model_inference(
            model=model,
            telemetry_df=cur_telemetry,
            meta_or_device=model_meta,
        )
        pred_idx = model_inference.pred_idx
        model_pred_name = model_inference.pred_name
        model_probs = model_inference.probs
        model_confidence = float(model_probs[pred_idx])

    # Structured TSLM supervisory target output
    tslm_report = format_tslm_explanation(rec_row, cur_telemetry)

    # ------------------ HEADER DASHBOARD ------------------
    st.title("⚡ Wind Turbine SCADA & Diagnostic Visualizer")
    st.caption(
        f"**Active Fleet Asset:** `{rec_row['turbine_id']}` ({rec_row['wind_farm']} Wind Farm, {rec_row['turbine_model']}) &nbsp;|&nbsp; "
        f"**Monitored Window:** `{selected_record_id}` &nbsp;|&nbsp; "
        f"**Timespan:** `{rec_row['start_time'].strftime('%Y-%m-%d %H:%M')}` to `{rec_row['end_time'].strftime('%Y-%m-%d %H:%M')} UTC` (12 Hours)"
    )

    # ------------------ TABS ------------------
    tab_diag, tab_telemetry, tab_power, tab_compare, tab_fleet, tab_raw = st.tabs(
        [
            "🧠 Timeframe Diagnosis & Model Output",
            "📈 Multi-Sensor Telemetry (8 Channels)",
            "🌪️ Power Curve & Aerodynamics",
            "⚖️ Baseline Comparison",
            "🛰️ Fleet & Farm Overview",
            "💾 Raw Telemetry & Export",
        ]
    )

    # ==================== TAB 1: TIMEFRAME DIAGNOSIS & MODEL PIPELINE ====================
    with tab_diag:
        st.subheader("🔬 Diagnostic Pipeline: Data ➔ Processing ➔ Model Output")
        st.caption(
            "Clear breakdown of the three stages: (1) What is in the raw SCADA data, "
            "(2) What the neural network ingested and processed, and (3) What the model output."
        )

        # High-level pipeline stage summary banner
        st.markdown(
            """
            <div style="background: linear-gradient(90deg, rgba(59,130,246,0.12) 0%, rgba(139,92,246,0.12) 50%, rgba(16,185,129,0.12) 100%); border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 12px; padding: 16px; margin-bottom: 24px;">
                <div style="display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; align-items: center; gap: 8px; text-align: center;">
                    <div style="padding: 8px;">
                        <span style="font-size: 1.3rem;">📥</span>
                        <div style="font-weight: 800; font-size: 0.85rem; color: #3B82F6; text-transform: uppercase;">1. In the Data</div>
                        <div style="font-size: 0.75rem; color: gray; margin-top: 2px;">Raw 10-min SCADA + Ground Truth Operator Event</div>
                    </div>
                    <div style="font-size: 1.4rem; color: gray;">➔</div>
                    <div style="padding: 8px;">
                        <span style="font-size: 1.3rem;">⚙️</span>
                        <div style="font-weight: 800; font-size: 0.85rem; color: #8B5CF6; text-transform: uppercase;">2. Processed by Model</div>
                        <div style="font-size: 0.75rem; color: gray; margin-top: 2px;">(1, 72, 8) Z-Score Normalized Tensor + Patch Tokens</div>
                    </div>
                    <div style="font-size: 1.4rem; color: gray;">➔</div>
                    <div style="padding: 8px;">
                        <span style="font-size: 1.3rem;">📤</span>
                        <div style="font-weight: 800; font-size: 0.85rem; color: #10B981; text-transform: uppercase;">3. Output from Model</div>
                        <div style="font-size: 0.75rem; color: gray; margin-top: 2px;">Softmax Predictions + 5-Part TSLM Diagnostic Report</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ------------------ STAGE 1: IN THE DATA ------------------
        st.markdown("### 📥 Stage 1: What is in the Data?")
        st.caption(
            "Raw physical observations and historical SCADA operator logs recorded for this timeframe."
        )

        gt_color = FAULT_COLOR_MAP.get(rec_row["fault_class"], "#3B82F6")
        gt_icon = FAULT_ICONS.get(rec_row["fault_class"], "📌")

        subsystem_color = SUBSYSTEM_COLOR_MAP.get(gt_subsystem, "#3B82F6")
        subsystem_icon = SUBSYSTEM_ICONS.get(gt_subsystem, "⚙️")
        triage_color = TRIAGE_COLOR_MAP.get(gt_triage, "#10B981")
        triage_icon = TRIAGE_ICONS.get(gt_triage, "🟢")

        col_d1, col_d2 = st.columns([1.1, 0.9])
        with col_d1:
            st.markdown(
                f"""
                <div style="background-color: var(--secondary-background-color); border-left: 5px solid #3B82F6; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;">
                    <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: #3B82F6;">Raw Telemetry Signals Recorded ({len(cur_telemetry)} Timesteps &middot; 8 Channels)</div>
                    <div style="font-size: 0.85rem; margin-top: 6px; line-height: 1.5;">
                        &bull; <b>Asset</b>: <code>{rec_row["turbine_id"]}</code> ({rec_row["wind_farm"]} Wind Farm)<br/>
                        &bull; <b>Hardware Specification</b>: {rec_row["turbine_model"]} (Rated: 2,050 kW, Hub Ht: 59&ndash;70m)<br/>
                        &bull; <b>Time Window</b>: <code>{rec_row["start_time"].strftime("%Y-%m-%d %H:%M")}</code> to <code>{rec_row["end_time"].strftime("%Y-%m-%d %H:%M")} UTC</code> ({len(cur_telemetry) * 10 / 60:.1f} Hours @ 10-min cadence)<br/>
                        &bull; <b>Continuous Channels</b>: Wind Speed (m/s), Power (kW), Rotor RPM, Gen RPM, Gear Oil Temp (&deg;C), Bearing Temp (&deg;C), Pitch Angle (&deg;), Vibration (mm/s&sup2;)
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_d2:
            st.markdown(
                f"""
                <div style="background-color: var(--secondary-background-color); border-left: 5px solid {subsystem_color}; border-radius: 8px; padding: 14px 18px; margin-bottom: 12px;">
                    <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: gray;">Verified SCADA Operator Ground Truth</div>
                    <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px;">
                        <span style="font-size: 1.2rem; font-weight: 800; color: {subsystem_color};">{subsystem_icon} {gt_subsystem}</span>
                        <span style="background-color: {triage_color}22; border: 1px solid {triage_color}; color: {triage_color}; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;">
                            {triage_icon} {gt_triage.upper()}
                        </span>
                    </div>
                    <div style="font-size: 0.78rem; color: gray; margin-top: 6px; line-height: 1.4;">
                        <b>Operator Category</b>: {gt_icon} {rec_row["fault_class"]}<br/>
                        <b>Logged Alarm / Rationale</b>: <code>{rec_row.get("rationale") or "Nominal generation (No active alarm)"}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.info(
            "🔒 **Strict Zero-Leakage Challenge Rule**: The alarm message, error code, and status category are "
            "historical ground truth from the SCADA log. **They are NEVER fed into the model as inputs** — "
            "they serve strictly as the evaluation answer that the model must discover from the sensors alone."
        )

        st.markdown("---")

        # ------------------ STAGE 2: PROCESSED BY THE MODEL ------------------
        st.markdown("### ⚙️ Stage 2: What Was Processed by the Model?")
        st.caption(
            "The continuous numerical feature space, patch tokenizer representations, and prompt context ingested by OpenTSLM."
        )

        p1, p2, p3 = st.columns(3)
        with p1:
            st.metric(
                "Input Tensor Dimensions",
                f"1 × {len(cur_telemetry)} × 8",
                "Batch × Steps × Physical Channels",
            )
        with p2:
            st.metric(
                "Temporal Patch Tokens",
                f"{len(cur_telemetry) // 4} Tokens",
                "Conv1d (k=4, s=4, d=256)",
            )
        with p3:
            proj_dim = (
                768
                if (model_meta and model_meta.get("type") == "softprompt")
                else 512
            )
            proj_label = (
                "LLM Soft Prompt Prefix"
                if (model_meta and model_meta.get("type") == "softprompt")
                else "LLM Latent Projection"
            )
            st.metric(
                proj_label,
                f"{proj_dim} Dimensions",
                "MLP Projector -> GPT-2 Backbone"
                if (model_meta and model_meta.get("type") == "softprompt")
                else "2-layer MLP Projector",
            )

        # Telemetry channel summary table
        sig_order = [
            "wind_speed",
            "power",
            "rotor_speed",
            "generator_rpm",
            "gear_oil_temp",
            "gen_bearing_temp",
            "pitch_angle",
            "drivetrain_accel",
        ]
        channel_summary = []
        for s in sig_order:
            series = cur_telemetry[s]
            mu = series.mean()
            sigma = series.std() + 1e-6
            channel_summary.append(
                {
                    "Sensor Channel": s,
                    "Unit": SIGNAL_META[s].unit,
                    "Window Mean": round(float(mu), 2),
                    "Window Std Dev": round(float(sigma), 2),
                    "Observed Range [Min, Max]": f"[{series.min():.1f}, {series.max():.1f}]",
                    "Description": SIGNAL_META[s].description,
                }
            )

        with st.expander(
            "🔍 Inspect Channel Statistics Processed by the Neural Network"
        ):
            st.dataframe(
                pd.DataFrame(channel_summary), use_container_width=True, hide_index=True
            )
            st.caption(
                "Continuous 10-minute SCADA measurements across the 12-hour observation window."
            )

        if rec_row.get("prompt"):
            with st.expander(
                "💬 Inspect Natural Language Prompt Context Ingested with the Tensor"
            ):
                st.code(rec_row["prompt"], language="markdown")

        with st.expander(
            "🔢 Inspect Exact Numerical Tensor Matrix (72 × 8) Fed into PyTorch"
        ):
            raw_mat = cur_telemetry[sig_order].values.astype(np.float32)
            st.dataframe(
                pd.DataFrame(
                    raw_mat, columns=sig_order, index=cur_telemetry.index
                ).round(2),
                use_container_width=True,
            )

        st.markdown("---")

        # ------------------ STAGE 3: OUTPUT FROM THE MODEL & TARGET ------------------
        st.markdown("### 📤 Stage 3: Ground Truth Benchmark vs Live Neural Model Output")
        st.caption(
            "Clear, transparent demarcation between verified historical SCADA ground truth and the neural network's live inferences."
        )

        st.info(
            "💡 **Demarcation & Zero-Leakage Protocol**:\n\n"
            "• 🏷️ **Ground Truth (Left Column)**: Derived strictly from Greenbyte operator alarm records and physical SCADA formulas. Specifies what actually happened on the turbine.\n\n"
            "• 🤖 **Neural Model Live Output (Right Column)**: Generated exclusively from continuous numerical sensor measurements ($1 \\times N \\times 8$). OpenTSLM outputs discrete subsystem predictions, operational triage, and autoregressive Chain-of-Thought diagnostic explanations in real time without seeing any alarm text."
        )

        col_gt, col_model = st.columns([1.05, 0.95], gap="medium")

        with col_gt:
            st.markdown(
                f"""
                <div style="background-color: var(--secondary-background-color); border: 2px solid #3B82F6; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="font-size: 0.8rem; font-weight: 800; color: #3B82F6; text-transform: uppercase;">
                            🏷️ Verified Historical Ground Truth
                        </span>
                        <span style="background: rgba(59, 130, 246, 0.15); color: #3B82F6; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;">
                            SCADA Log + Physics Rules
                        </span>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
                        <div style="background: var(--background-color); padding: 8px 12px; border-radius: 6px; border-left: 4px solid {subsystem_color};">
                            <div style="font-size: 0.7rem; color: gray; text-transform: uppercase; font-weight: 600;">Ground Truth Subsystem</div>
                            <div style="font-size: 0.95rem; font-weight: 800; color: {subsystem_color};">{subsystem_icon} {gt_subsystem}</div>
                        </div>
                        <div style="background: var(--background-color); padding: 8px 12px; border-radius: 6px; border-left: 4px solid {triage_color};">
                            <div style="font-size: 0.7rem; color: gray; text-transform: uppercase; font-weight: 600;">Operational Triage</div>
                            <div style="font-size: 0.95rem; font-weight: 800; color: {triage_color};">{triage_icon} {gt_triage.upper()}</div>
                        </div>
                    </div>
                    <div style="font-size: 0.8rem; line-height: 1.4; color: var(--text-color);">
                        &bull; <b>Operator Fault Category</b>: {gt_icon} {rec_row["fault_class"]}<br/>
                        &bull; <b>Historical Alarm / Rationale</b>: <code>{rec_row.get("rationale") or "Nominal generation (No active alarm)"}</code><br/>
                        &bull; <b>Telemetry Verification Flags</b>: {', '.join(f'<code>{f}</code>' for f in gt_telemetry_flags) if gt_telemetry_flags else '<em>Nominal physical envelope (No sensor flags)</em>'}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Supervisory Target Report (5-line)
            st.markdown("#### 📋 Rule-Grounded Supervisory Target (Task T1 Standard)")
            st.caption(
                "🏷️ **Deterministic Target Specification — NOT generated by model.** "
                "Defines the engineering rationale benchmark that models are trained to emulate:"
            )
            st.markdown(
                f"""
                <div style="background-color: var(--secondary-background-color); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 14px; margin-bottom: 16px; font-size: 0.85rem;">
                    <div style="margin-bottom: 10px;">
                        <span style="color: #3B82F6; font-weight: 700; text-transform: uppercase; font-size: 0.72rem;">1. FINDING (Target)</span>
                        <div style="padding-left: 8px; border-left: 2px solid #3B82F6; margin-top: 2px;">{tslm_report["finding"]}</div>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <span style="color: #8B5CF6; font-weight: 700; text-transform: uppercase; font-size: 0.72rem;">2. EVIDENCE (Target)</span>
                        <div style="padding-left: 8px; border-left: 2px solid #8B5CF6; margin-top: 2px;">{tslm_report["evidence"]}</div>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <span style="color: #EF4444; font-weight: 700; text-transform: uppercase; font-size: 0.72rem;">3. CAUSE (Target)</span>
                        <div style="padding-left: 8px; border-left: 2px solid #EF4444; margin-top: 2px;">{tslm_report["cause"]}</div>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <span style="color: #F59E0B; font-weight: 700; text-transform: uppercase; font-size: 0.72rem;">4. IMPACT (Target)</span>
                        <div style="padding-left: 8px; border-left: 2px solid #F59E0B; margin-top: 2px;">{tslm_report["impact"]}</div>
                    </div>
                    <div style="margin-bottom: 10px;">
                        <span style="color: #10B981; font-weight: 700; text-transform: uppercase; font-size: 0.72rem;">5. ACTION (Target)</span>
                        <div style="padding-left: 8px; border-left: 2px solid #10B981; margin-top: 2px; font-weight: 500;">{tslm_report["action"]}</div>
                    </div>
                    <div style="padding-top: 8px; border-top: 1px dashed rgba(128, 128, 128, 0.3); font-family: monospace; font-weight: 700; color: {subsystem_color};">
                        Target Answer: <b>{gt_subsystem}</b> ({rec_row['fault_class']})
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_model:
            if model_inference is not None and model_meta is not None:
                model_type_label = (
                    "OpenTSLM-SoftPrompt (LoRA GPT-2)"
                    if model_inference.model_type == "softprompt"
                    else "OpenTSLM Encoder (5-Class)"
                )
                model_color = (
                    "#8B5CF6"
                    if model_inference.model_type == "softprompt"
                    else "#3B82F6"
                )

                pred_subsystem = model_inference.parsed_subsystem
                pred_triage = model_inference.parsed_triage
                pred_sub_color = SUBSYSTEM_COLOR_MAP.get(
                    pred_subsystem, "#8B5CF6"
                )
                pred_sub_icon = SUBSYSTEM_ICONS.get(pred_subsystem, "🤖")
                pred_tri_color = TRIAGE_COLOR_MAP.get(pred_triage, "#10B981")
                pred_tri_icon = TRIAGE_ICONS.get(pred_triage, "🟢")

                is_sub_match = (pred_subsystem == gt_subsystem) or (
                    model_inference.coarse_fault == rec_row["fault_class"]
                )
                sub_badge = "🎯 ACCURATE" if is_sub_match else "⚠️ DISCREPANCY"
                sub_badge_color = "#10B981" if is_sub_match else "#EF4444"

                is_tri_match = pred_triage.lower() == gt_triage.lower()
                tri_badge = "🎯 CONCORDANT" if is_tri_match else "⚠️ DIVERGENT"
                tri_badge_color = "#10B981" if is_tri_match else "#EF4444"

                st.markdown(
                    f"""
                    <div style="background-color: var(--secondary-background-color); border: 2px solid {model_color}; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <span style="font-size: 0.8rem; font-weight: 800; color: {model_color}; text-transform: uppercase;">
                                🤖 Live Neural Network Inference
                            </span>
                            <span style="background: {model_color}22; color: {model_color}; font-size: 0.72rem; font-weight: 700; padding: 2px 8px; border-radius: 4px;">
                                {model_type_label} &middot; Epoch {model_meta.get('epoch', 1)}
                            </span>
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
                            <div style="background: var(--background-color); padding: 8px 12px; border-radius: 6px; border-left: 4px solid {pred_sub_color};">
                                <div style="display: flex; justify-content: space-between;">
                                    <span style="font-size: 0.7rem; color: gray; text-transform: uppercase; font-weight: 600;">Inferred Subsystem</span>
                                    <span style="font-size: 0.65rem; color: {sub_badge_color}; font-weight: 700;">{sub_badge}</span>
                                </div>
                                <div style="font-size: 0.95rem; font-weight: 800; color: {pred_sub_color};">{pred_sub_icon} {pred_subsystem}</div>
                            </div>
                            <div style="background: var(--background-color); padding: 8px 12px; border-radius: 6px; border-left: 4px solid {pred_tri_color};">
                                <div style="display: flex; justify-content: space-between;">
                                    <span style="font-size: 0.7rem; color: gray; text-transform: uppercase; font-weight: 600;">Inferred Triage</span>
                                    <span style="font-size: 0.65rem; color: {tri_badge_color}; font-weight: 700;">{tri_badge}</span>
                                </div>
                                <div style="font-size: 0.95rem; font-weight: 800; color: {pred_tri_color};">{pred_tri_icon} {pred_triage.upper()}</div>
                            </div>
                        </div>
                        <div style="font-size: 0.78rem; color: gray;">
                            Classifier Confidence: <b>{model_confidence * 100:.1f}%</b> &nbsp;|&nbsp; Device: <code>{model_meta.get('device', 'cpu')}</code>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Softmax Probability Distribution Bar Chart
                st.markdown("##### 📊 Neural Softmax Probability Distribution (Live)")
                prob_classes = model_inference.classes
                prob_df = pd.DataFrame(
                    {
                        "Class": prob_classes,
                        "Probability": model_inference.probs,
                    }
                )
                prob_df = prob_df.sort_values("Probability", ascending=True).tail(6)
                fig_prob = px.bar(
                    prob_df,
                    x="Probability",
                    y="Class",
                    orientation="h",
                    text=prob_df["Probability"].apply(lambda p: f"{p * 100:.1f}%"),
                    color="Class",
                )
                fig_prob.update_layout(
                    height=200,
                    margin={"l": 10, "r": 10, "t": 5, "b": 5},
                    xaxis={"range": [0, 1.05], "tickformat": ".0%"},
                    showlegend=False,
                )
                st.plotly_chart(fig_prob, use_container_width=True)

                # Live Autoregressively Generated Diagnosis
                if model_inference.generated_text:
                    st.markdown(
                        "##### 💬 Autoregressive Chain-of-Thought Diagnosis (Live LLM)"
                    )
                    st.caption(
                        "🧠 **Generated token-by-token by LoRA GPT-2 conditioned on continuous telemetry soft prompt embeddings:**"
                    )
                    st.markdown(
                        f"""
                        <div style="background-color: #0F172A; border: 1px solid #334155; border-radius: 8px; padding: 14px; font-family: monospace; font-size: 0.85rem; color: #E2E8F0; line-height: 1.5; white-space: pre-wrap; margin-bottom: 16px;">
{model_inference.generated_text}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                else:
                    st.info(
                        "ℹ️ **Discrete Encoder Baseline Active**: The encoder model outputs discrete logits without natural language generation. "
                        "Select **'OpenTSLM-SoftPrompt'** in the sidebar to activate live autoregressive diagnostic text generation."
                    )
            else:
                st.warning(
                    "⚠️ No trained OpenTSLM model checkpoint loaded. Train the model using `mk/src/models/train.py`."
                )

    # ==================== TAB 2: MULTI-SENSOR TELEMETRY ====================
    with tab_telemetry:
        st.subheader(
            f"📈 8-Channel SCADA Telemetry: {selected_record_id} ({rec_row['turbine_id']})"
        )

        plot_df = cur_telemetry.copy()
        if unit_mode == "Normalized (Z-Score)":
            plot_df = (plot_df - plot_df.mean()) / (plot_df.std() + 1e-6)
        elif unit_mode == "Min-Max Normalized [0, 1]":
            plot_df = (plot_df - plot_df.min()) / (plot_df.max() - plot_df.min() + 1e-6)

        layout_mode = st.radio(
            "Visualization Layout:",
            [
                "Subsystem Grouped (3 Panels)",
                "Stacked (All Channels)",
                "Unified Overlay",
            ],
            horizontal=True,
        )

        if layout_mode == "Subsystem Grouped (3 Panels)":
            fig_sync = make_subplots(
                rows=3,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.07,
                subplot_titles=[
                    "🌬️ Aerodynamics & Generation (Wind Speed, Power, Blade Pitch)",
                    "⚙️ Mechanical Drive Train (Rotor RPM, Generator RPM, Vibration)",
                    "🌡️ Thermal Circuits (Gear Oil Temp, Bearing Temp)",
                ],
            )

            # Panel 1: Aero
            for col_name, color in [
                ("wind_speed", "#3B82F6"),
                ("power", "#10B981"),
                ("pitch_angle", "#8B5CF6"),
            ]:
                if col_name in visible_signals and col_name in plot_df:
                    fig_sync.add_trace(
                        go.Scatter(
                            x=plot_df.index,
                            y=plot_df[col_name],
                            name=f"{col_name} ({SIGNAL_META[col_name].unit})",
                            line={"color": color, "width": 2},
                        ),
                        row=1,
                        col=1,
                    )

            # Panel 2: Mech
            for col_name, color in [
                ("rotor_speed", "#F59E0B"),
                ("generator_rpm", "#EC4899"),
                ("drivetrain_accel", "#EF4444"),
            ]:
                if col_name in visible_signals and col_name in plot_df:
                    fig_sync.add_trace(
                        go.Scatter(
                            x=plot_df.index,
                            y=plot_df[col_name],
                            name=f"{col_name} ({SIGNAL_META[col_name].unit})",
                            line={"color": color, "width": 2},
                        ),
                        row=2,
                        col=1,
                    )

            # Panel 3: Thermal
            for col_name, color in [
                ("gear_oil_temp", "#DC2626"),
                ("gen_bearing_temp", "#D97706"),
            ]:
                if col_name in visible_signals and col_name in plot_df:
                    fig_sync.add_trace(
                        go.Scatter(
                            x=plot_df.index,
                            y=plot_df[col_name],
                            name=f"{col_name} ({SIGNAL_META[col_name].unit})",
                            line={"color": color, "width": 2},
                        ),
                        row=3,
                        col=1,
                    )

            fig_sync.update_layout(
                height=720,
                margin={"l": 30, "r": 20, "t": 40, "b": 30},
                hovermode="x unified",
            )
            st.plotly_chart(fig_sync, use_container_width=True)

        elif layout_mode == "Stacked (All Channels)":
            channels_to_plot = [c for c in visible_signals if c in plot_df]
            fig_stack = make_subplots(
                rows=len(channels_to_plot),
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=[
                    f"{c} ({SIGNAL_META[c].unit})" for c in channels_to_plot
                ],
            )
            for i, c in enumerate(channels_to_plot):
                fig_stack.add_trace(
                    go.Scatter(
                        x=plot_df.index, y=plot_df[c], name=c, line={"width": 2}
                    ),
                    row=i + 1,
                    col=1,
                )
            fig_stack.update_layout(
                height=160 * len(channels_to_plot),
                margin={"l": 30, "r": 20, "t": 30, "b": 30},
                hovermode="x unified",
            )
            st.plotly_chart(fig_stack, use_container_width=True)

        else:
            fig_ov = go.Figure()
            for c in visible_signals:
                if c in plot_df:
                    fig_ov.add_trace(
                        go.Scatter(
                            x=plot_df.index,
                            y=plot_df[c],
                            name=f"{c} ({SIGNAL_META[c].unit})",
                            line={"width": 2},
                        )
                    )
            fig_ov.update_layout(
                height=480,
                margin={"l": 30, "r": 20, "t": 30, "b": 30},
                hovermode="x unified",
                title=f"Unified Telemetry Overlay: {selected_record_id}",
            )
            st.plotly_chart(fig_ov, use_container_width=True)

        # Statistical Metrics Table
        st.markdown("#### 📐 Window Telemetry Statistical Metrics")
        stats_rows = []
        for c in visible_signals:
            if c in cur_telemetry:
                series = cur_telemetry[c]
                start_v = series.iloc[0]
                end_v = series.iloc[-1]
                delta_v = end_v - start_v
                stats_rows.append(
                    {
                        "Signal": c,
                        "Unit": SIGNAL_META[c].unit,
                        "Mean": round(float(series.mean()), 2),
                        "Std Dev": round(float(series.std()), 2),
                        "Min": round(float(series.min()), 2),
                        "Median": round(float(series.median()), 2),
                        "Max": round(float(series.max()), 2),
                        "Start": round(float(start_v), 2),
                        "End": round(float(end_v), 2),
                        "Delta": f"{delta_v:+.2f}",
                    }
                )
        st.dataframe(
            pd.DataFrame(stats_rows), use_container_width=True, hide_index=True
        )

    # ==================== TAB 3: POWER CURVE & AERODYNAMICS ====================
    with tab_power:
        st.subheader("🌪️ Aerodynamic Performance & Power Curves")
        st.caption(
            "Evaluate aerodynamic conversion efficiency against the theoretical Senvion power curve."
        )

        turbine_model = rec_row["turbine_model"]
        ws_ref = np.linspace(0, 25, 200)
        p_ref = compute_theoretical_power(ws_ref, model=turbine_model)

        col_curve, col_corr = st.columns([1.2, 0.8])

        with col_curve:
            st.markdown(f"#### SCADA Power Curve vs {turbine_model} Theoretical Model")
            fig_power = go.Figure()
            # Background cloud from filtered records
            sample_rids = filtered_records["record_id"].tolist()[:30]
            bg_dfs = [telemetry_dict[rid].assign(record_id=rid) for rid in sample_rids]
            if bg_dfs:
                bg_combined = pd.concat(bg_dfs, ignore_index=True)
                fig_power.add_trace(
                    go.Scatter(
                        x=bg_combined["wind_speed"],
                        y=bg_combined["power"],
                        mode="markers",
                        name="Fleet Context (Filtered)",
                        marker={"size": 4, "color": "rgba(148, 163, 184, 0.3)"},
                    )
                )

            # Current window points
            fig_power.add_trace(
                go.Scatter(
                    x=cur_telemetry["wind_speed"],
                    y=cur_telemetry["power"],
                    mode="markers+lines",
                    name=f"Current Window ({rec_row['fault_class']})",
                    marker={
                        "size": 8,
                        "color": FAULT_COLOR_MAP.get(rec_row["fault_class"], "#EF4444"),
                    },
                    line={
                        "color": FAULT_COLOR_MAP.get(rec_row["fault_class"], "#EF4444"),
                        "width": 1.5,
                    },
                )
            )

            # Theoretical line
            fig_power.add_trace(
                go.Scatter(
                    x=ws_ref,
                    y=p_ref,
                    mode="lines",
                    name=f"Theoretical {turbine_model} (2050 kW)",
                    line={"color": "#1E293B", "width": 3, "dash": "dash"},
                )
            )

            fig_power.update_layout(
                xaxis_title="Wind Speed (m/s)",
                yaxis_title="Electrical Active Power (kW)",
                height=440,
                margin={"l": 20, "r": 20, "t": 30, "b": 20},
                legend={"orientation": "h", "y": -0.25, "x": 0.5, "xanchor": "center"},
            )
            st.plotly_chart(fig_power, use_container_width=True)

        with col_corr:
            st.markdown("#### Sensor Cross-Correlation Heatmap")
            corr_mat = cur_telemetry[SIGNAL_NAMES].corr()
            fig_corr = px.imshow(
                corr_mat,
                text_auto=".2f",
                color_continuous_scale="RdBu_r",
                zmin=-1,
                zmax=1,
            )
            fig_corr.update_layout(
                height=440, margin={"l": 20, "r": 20, "t": 30, "b": 20}
            )
            st.plotly_chart(fig_corr, use_container_width=True)

    # ==================== TAB 4: BASELINE COMPARISON ====================
    with tab_compare:
        st.subheader("⚖️ Selected Window vs Nominal Operating Baseline")
        st.caption(
            "Isolate anomalous sensor signatures by comparing against a healthy operating window on the same or sister turbine."
        )

        # Find healthy normal windows
        normal_pool = df_all_records[
            df_all_records["fault_class"] == "Normal Operation"
        ]
        same_turb_normals = normal_pool[
            normal_pool["turbine_id"] == rec_row["turbine_id"]
        ]
        baseline_candidates = (
            same_turb_normals if not same_turb_normals.empty else normal_pool
        )

        col_b1, col_b2 = st.columns([1.2, 0.8])
        with col_b1:
            baseline_rec_id = st.selectbox(
                "Select Normal Baseline Window:",
                baseline_candidates["record_id"].tolist(),
                format_func=lambda rid: (
                    f"{rid} | {df_all_records.loc[df_all_records['record_id'] == rid, 'turbine_id'].values[0]} | {df_all_records.loc[df_all_records['record_id'] == rid, 'start_time'].values[0]}"
                ),
            )
        with col_b2:
            comp_signal = st.selectbox("Signal to Compare:", SIGNAL_NAMES, index=0)

        baseline_df = telemetry_dict[baseline_rec_id]
        cur_vals = cur_telemetry[comp_signal].values
        base_vals = baseline_df[comp_signal].values
        residual = cur_vals - base_vals
        elapsed_min = np.arange(len(cur_vals)) * 10

        fig_comp = go.Figure()
        fig_comp.add_trace(
            go.Scatter(
                x=elapsed_min,
                y=cur_vals,
                name=f"Current: {selected_record_id} ({rec_row['fault_class']})",
                line={
                    "color": FAULT_COLOR_MAP.get(rec_row["fault_class"], "#EF4444"),
                    "width": 2.5,
                },
            )
        )
        fig_comp.add_trace(
            go.Scatter(
                x=elapsed_min,
                y=base_vals,
                name=f"Baseline: {baseline_rec_id} (Normal Operation)",
                line={"color": "#10B981", "width": 2, "dash": "dash"},
            )
        )
        fig_comp.add_trace(
            go.Bar(
                x=elapsed_min,
                y=residual,
                name="Residual Deviation (Current - Baseline)",
                marker={"color": "rgba(148, 163, 184, 0.4)"},
            )
        )
        fig_comp.update_layout(
            title=f"12-Hour Trajectory Comparison: {SIGNAL_META[comp_signal].description} ({SIGNAL_META[comp_signal].unit})",
            xaxis_title="Elapsed Time (Minutes)",
            yaxis_title=f"{comp_signal} ({SIGNAL_META[comp_signal].unit})",
            height=460,
            hovermode="x unified",
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
        )
        st.plotly_chart(fig_comp, use_container_width=True)

    # ==================== TAB 5: FLEET & FARM OVERVIEW ====================
    with tab_fleet:
        st.subheader("🛰️ Dual Wind Farm Fleet Overview (Penmanshiel & Kelmarsh)")

        # Summary KPIs
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        with k1:
            st.metric("Total Turbines", "20 Assets", "14 Pen + 6 Kel")
        with k2:
            st.metric("Total Windows", f"{len(df_all_records):,}", "600 Windows")
        with k3:
            st.metric(
                "Total Telemetry Time",
                f"{len(df_all_records) * 12:,} Hours",
                "7,200 Monitored Hrs",
            )
        with k4:
            anom_count = len(
                df_all_records[df_all_records["fault_class"] != "Normal Operation"]
            )
            st.metric(
                "Fault Windows",
                f"{anom_count}",
                f"{anom_count / len(df_all_records) * 100:.1f}%",
            )
        with k5:
            st.metric("SCADA Channels", "8 Continuous", "10-min Resolution")
        with k6:
            st.metric("Fault Classes", "5 Categories", "Zero-leakage split")

        st.markdown("---")
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            st.markdown("#### 🏴󠁧󠁢󠁳󠁣󠁴󠁿 Penmanshiel Wind Farm (14 Turbines)")
            st.caption(
                "Training & In-Domain Testbed (Scottish Borders, UK) &middot; Senvion MM82 (2.05 MW)"
            )
            ct_pen = pd.crosstab(
                df_all_records[df_all_records["wind_farm"] == "Penmanshiel"][
                    "turbine_id"
                ],
                df_all_records[df_all_records["wind_farm"] == "Penmanshiel"][
                    "fault_class"
                ],
            )
            fig_pen = px.bar(
                ct_pen.reset_index(),
                x="turbine_id",
                y=list(ct_pen.columns),
                title="Penmanshiel Windows per Turbine",
                color_discrete_map=FAULT_COLOR_MAP,
                barmode="stack",
            )
            fig_pen.update_layout(
                height=340,
                margin={"l": 10, "r": 10, "t": 30, "b": 10},
                showlegend=False,
            )
            st.plotly_chart(fig_pen, use_container_width=True)

        with col_f2:
            st.markdown("#### 🇬🇧 Kelmarsh Wind Farm (6 Turbines)")
            st.caption(
                "Unseen Cross-Farm Zero-Shot Demo (Northamptonshire, UK) &middot; Senvion MM92 (2.05 MW)"
            )
            ct_kel = pd.crosstab(
                df_all_records[df_all_records["wind_farm"] == "Kelmarsh"]["turbine_id"],
                df_all_records[df_all_records["wind_farm"] == "Kelmarsh"][
                    "fault_class"
                ],
            )
            fig_kel = px.bar(
                ct_kel.reset_index(),
                x="turbine_id",
                y=list(ct_kel.columns),
                title="Kelmarsh Windows per Turbine",
                color_discrete_map=FAULT_COLOR_MAP,
                barmode="stack",
            )
            fig_kel.update_layout(
                height=340, margin={"l": 10, "r": 10, "t": 30, "b": 10}
            )
            st.plotly_chart(fig_kel, use_container_width=True)

        # Static specifications table
        st.markdown("---")
        st.markdown("#### ⚙️ Fleet Technical Specifications")
        fleet_specs = pd.DataFrame(
            [
                {
                    "Wind Farm": "Penmanshiel",
                    "Location": "Scottish Borders, UK",
                    "Turbine Count": 14,
                    "Turbine Model": "Senvion MM82",
                    "Rotor Diameter": "82 meters",
                    "Hub Height": "59 - 70 meters",
                    "Rated Power": "2,050 kW (2.05 MW)",
                    "Role": "Model Training & In-Domain Benchmark",
                },
                {
                    "Wind Farm": "Kelmarsh",
                    "Location": "Northamptonshire, UK",
                    "Turbine Count": 6,
                    "Turbine Model": "Senvion MM92",
                    "Rotor Diameter": "92 meters",
                    "Hub Height": "70 meters",
                    "Rated Power": "2,050 kW (2.05 MW)",
                    "Role": "Unseen Cross-Farm Zero-Shot Demo",
                },
            ]
        )
        st.dataframe(fleet_specs, use_container_width=True, hide_index=True)

    # ==================== TAB 6: RAW DATA & EXPORT ====================
    with tab_raw:
        st.subheader("💾 Raw Telemetry Matrix & Annotation Metadata")

        col_r1, col_r2 = st.columns([1, 1])

        with col_r1:
            st.markdown(
                f"#### Telemetry Matrix: `{selected_record_id}` (72 timesteps × 8 sensors)"
            )
            st.dataframe(cur_telemetry, use_container_width=True)

            csv_bytes = cur_telemetry.to_csv().encode("utf-8")
            st.download_button(
                label=f"📥 Download {selected_record_id} SCADA CSV",
                data=csv_bytes,
                file_name=f"{selected_record_id}_telemetry.csv",
                mime="text/csv",
            )

        with col_r2:
            st.markdown("#### Record Annotations & Model Metadata")
            st.json(
                {
                    "record_id": rec_row["record_id"],
                    "wind_farm": rec_row["wind_farm"],
                    "turbine_id": rec_row["turbine_id"],
                    "turbine_model": rec_row["turbine_model"],
                    "fault_class": rec_row["fault_class"],
                    "start_time": str(rec_row["start_time"]),
                    "end_time": str(rec_row["end_time"]),
                    "sampling_frequency": "10 minutes",
                    "steps": WINDOW_STEPS,
                    "model_prediction": model_pred_name,
                    "model_confidence": f"{model_confidence * 100:.1f}%",
                    "prompt": rec_row.get("prompt"),
                    "tslm_structured_output": tslm_report,
                }
            )


if __name__ == "__main__":
    main()
