"""Dedicated Streamlit Visualizer for Wind Turbine SCADA Data Inspection.

Features:
- Full multi-channel SCADA telemetry inspection across 20 turbines (Penmanshiel & Kelmarsh).
- Interactive date & time selector (calendar picker, timestamp stepper, operational filters).
- Comprehensive SCADA event annotations (alarm logs, failure mechanism rationale, engineering actions).
- Turbine-to-turbine comparison (concurrent timestamp matching, dual-trace overlays, residuals).
- Multi-mode baseline comparison (nominal healthy baseline, fleet average envelope, theoretical IEC power curve).
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Setup system path to access project packages
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
        WINDOW_STEPS,
    )
except ImportError:
    from src.data.schemas import (
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        KELMARSH_DATASET_ID,
        PENMANSHIEL_DATASET_ID,
        SELECTED_SIGNALS,
        SIGNAL_NAMES,
        WINDOW_STEPS,
    )

# Fault styling & icons
FAULT_COLOR_MAP = {
    "Normal Operation": "#10B981",  # Emerald
    "Gearbox Overheating": "#EF4444",  # Crimson
    "Generator Bearing Anomaly": "#F59E0B",  # Amber
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

# Physical alert thresholds for SCADA channels
SIGNAL_THRESHOLDS = {
    "gear_oil_temp": {"warning": 65.0, "trip": 75.0, "unit": "°C"},
    "gen_bearing_temp": {"warning": 70.0, "trip": 85.0, "unit": "°C"},
    "drivetrain_accel": {"warning": 120.0, "trip": 250.0, "unit": "mm/s²"},
    "rotor_speed": {"warning": 17.5, "trip": 20.0, "unit": "RPM"},
    "generator_rpm": {"warning": 1700.0, "trip": 1900.0, "unit": "RPM"},
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
        return pd.read_csv(static_path)
    return pd.DataFrame()


@st.cache_data(show_spinner="Loading SCADA telemetry records from TimeNet...")
def load_timenet_dataset(
    dataset_id: str = "energy/penmanshiel-wind-scada",
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
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
    turbine_model = "Senvion MM82 (2.05 MW)" if is_penmanshiel else "Senvion MM92 (2.05 MW)"

    for r in dataset.records:
        rec_id = r.record_id
        rec_data: Dict[str, Any] = {
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

        # Extract tasks & annotations
        tasks = [t for t in dataset.tasks if rec_id in t.record_ids]
        for t in tasks:
            if type(t).__name__ == "AnswerTask":
                rec_data["prompt"] = getattr(t, "prompt", "")
                rec_data["target"] = getattr(t, "target", "")
                rec_data["rationale"] = getattr(t, "rationale", "")

        # Time series telemetry
        sig_map = {}
        for ts in r.time_series:
            sig_map[ts.signal] = ts.to_numpy()

        n_steps = len(next(iter(sig_map.values()))) if sig_map else WINDOW_STEPS
        rec_data["end_time"] = rec_data["start_time"] + pd.Timedelta(minutes=10 * n_steps)

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
def load_all_wind_farms() -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """Loads and combines all records from both Penmanshiel and Kelmarsh wind farms."""
    df_pen, tel_pen = load_timenet_dataset(PENMANSHIEL_DATASET_ID)
    df_kel, tel_kel = load_timenet_dataset(KELMARSH_DATASET_ID)

    df_combined = pd.concat([df_pen, df_kel], ignore_index=True)
    tel_combined = {**tel_pen, **tel_kel}
    return df_combined, tel_combined


def compute_theoretical_power(wind_speeds: np.ndarray, model: str = "MM92") -> np.ndarray:
    """Compute theoretical Senvion MM82/MM92 power curve (rated 2050 kW)."""
    cut_in = 3.0
    rated_speed = 12.5 if "MM92" in model else 13.0
    cut_out = 25.0
    rated_power = 2050.0

    p = np.zeros_like(wind_speeds, dtype=float)
    valid_mask = (wind_speeds >= cut_in) & (wind_speeds < rated_speed)
    p[valid_mask] = rated_power * ((wind_speeds[valid_mask] - cut_in) / (rated_speed - cut_in)) ** 3
    p[(wind_speeds >= rated_speed) & (wind_speeds <= cut_out)] = rated_power
    p[wind_speeds > cut_out] = 0.0
    p[wind_speeds < cut_in] = 0.0
    return p


def parse_event_annotations(rec_row: pd.Series, telemetry_df: pd.DataFrame) -> Dict[str, Any]:
    """Parse SCADA event annotation details, alarm logs, and engineering diagnosis."""
    fault_class = rec_row.get("fault_class", "Normal Operation")
    rationale = rec_row.get("rationale", "")
    target = rec_row.get("target", "")

    # Extract action from target text
    action = "No intervention required. Maintain routine supervisory monitoring."
    if "Action:" in target:
        action = target.split("Action:")[1].strip()

    # Create timestamped alarm events based on telemetry threshold crossings & operational status
    alarms = []
    if fault_class != "Normal Operation":
        # Check specific sensor triggers
        if fault_class == "Gearbox Overheating":
            high_oil = telemetry_df[telemetry_df["gear_oil_temp"] > 65.0]
            t_event = high_oil.index[0] if not high_oil.empty else telemetry_df.index[len(telemetry_df) // 2]
            alarms.append(
                {
                    "timestamp": t_event.strftime("%Y-%m-%d %H:%M UTC"),
                    "severity": "ALARM",
                    "code": "GBX-OIL-TEMP-HIGH",
                    "subsystem": "Gearbox Lubrication Circuit",
                    "message": f"Gear oil temperature reached {telemetry_df['gear_oil_temp'].max():.1f}°C (Threshold: 65.0°C).",
                }
            )
        elif fault_class == "Generator Bearing Anomaly":
            high_bear = telemetry_df[telemetry_df["gen_bearing_temp"] > 70.0]
            t_event = high_bear.index[0] if not high_bear.empty else telemetry_df.index[len(telemetry_df) // 2]
            alarms.append(
                {
                    "timestamp": t_event.strftime("%Y-%m-%d %H:%M UTC"),
                    "severity": "ALARM",
                    "code": "GEN-BEAR-DE-HIGH",
                    "subsystem": "Generator Drive-End Bearing",
                    "message": f"Drive-end bearing temperature surged to {telemetry_df['gen_bearing_temp'].max():.1f}°C.",
                }
            )
        elif fault_class == "Pitch / Aerodynamic Fault":
            high_vib = telemetry_df[telemetry_df["drivetrain_accel"] > 120.0]
            t_event = high_vib.index[0] if not high_vib.empty else telemetry_df.index[len(telemetry_df) // 2]
            alarms.append(
                {
                    "timestamp": t_event.strftime("%Y-%m-%d %H:%M UTC"),
                    "severity": "WARNING",
                    "code": "AERO-PITCH-ASYM",
                    "subsystem": "Pitch Control & Rotor Hub",
                    "message": f"Asymmetric blade pitch detected; drivetrain acceleration spiked to {telemetry_df['drivetrain_accel'].max():.1f} mm/s².",
                }
            )
        elif fault_class == "Turbine Trip / Forced Outage":
            low_pow = telemetry_df[(telemetry_df["power"] < 5.0) & (telemetry_df["wind_speed"] > 4.0)]
            t_event = low_pow.index[0] if not low_pow.empty else telemetry_df.index[len(telemetry_df) // 2]
            alarms.append(
                {
                    "timestamp": t_event.strftime("%Y-%m-%d %H:%M UTC"),
                    "severity": "TRIP / OUTAGE",
                    "code": "SAFETY-TRIP-FORCED",
                    "subsystem": "Safety Chain / Grid Converter",
                    "message": "Immediate turbine shutdown executed. Active power collapsed to 0 kW while wind > cut-in.",
                }
            )

    # If no anomaly alarms, add nominal supervisory heartbeat
    if not alarms:
        alarms.append(
            {
                "timestamp": rec_row["start_time"].strftime("%Y-%m-%d %H:%M UTC"),
                "severity": "INFO",
                "code": "SCADA-HEARTBEAT-OK",
                "subsystem": "All Subsystems Nominal",
                "message": "Continuous SCADA telemetry within normal engineering tolerances.",
            }
        )

    return {
        "fault_class": fault_class,
        "rationale": rationale,
        "action": action,
        "alarms": alarms,
    }


def find_concurrent_sister_window(
    df_all_records: pd.DataFrame,
    current_rec: pd.Series,
    sister_turbine_id: str,
) -> Optional[str]:
    """Finds the record ID of a sister turbine with the exact or closest concurrent start time."""
    sub_df = df_all_records[df_all_records["turbine_id"] == sister_turbine_id]
    if sub_df.empty:
        return None

    # Check exact match
    exact = sub_df[sub_df["start_time"] == current_rec["start_time"]]
    if not exact.empty:
        return str(exact["record_id"].iloc[0])

    # Find closest within 48 hours
    time_diffs = (sub_df["start_time"] - current_rec["start_time"]).abs()
    min_diff = time_diffs.min()
    if min_diff <= pd.Timedelta(hours=48):
        closest_idx = time_diffs.idxmin()
        return str(sub_df.loc[closest_idx, "record_id"])

    return str(sub_df["record_id"].iloc[0])


def find_matching_healthy_baseline(
    df_all_records: pd.DataFrame,
    telemetry_dict: Dict[str, pd.DataFrame],
    current_rec: pd.Series,
    current_telemetry: pd.DataFrame,
) -> Tuple[str, pd.DataFrame]:
    """Finds a healthy normal operation window that matches the current window's mean wind speed."""
    normals = df_all_records[df_all_records["fault_class"] == "Normal Operation"]
    # Prefer same turbine if available
    same_turb = normals[normals["turbine_id"] == current_rec["turbine_id"]]
    cand_df = same_turb if len(same_turb) >= 2 else normals

    current_wind = float(current_telemetry["wind_speed"].mean())
    best_rid = cand_df["record_id"].iloc[0]
    min_diff = 999.0

    for rid in cand_df["record_id"]:
        if rid == current_rec["record_id"]:
            continue
        tel = telemetry_dict.get(rid)
        if tel is not None and "wind_speed" in tel:
            diff = abs(float(tel["wind_speed"].mean()) - current_wind)
            if diff < min_diff:
                min_diff = diff
                best_rid = rid

    return best_rid, telemetry_dict[best_rid]


def compute_fleet_average_baseline(
    df_all_records: pd.DataFrame,
    telemetry_dict: Dict[str, pd.DataFrame],
    current_rec: pd.Series,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Computes mean and std of all operational sister turbines in the wind farm at concurrent times."""
    farm_records = df_all_records[
        (df_all_records["wind_farm"] == current_rec["wind_farm"])
        & (df_all_records["start_time"] == current_rec["start_time"])
        & (df_all_records["record_id"] != current_rec["record_id"])
    ]
    if farm_records.empty:
        # Fallback to healthy normal windows of the farm
        farm_records = df_all_records[
            (df_all_records["wind_farm"] == current_rec["wind_farm"])
            & (df_all_records["fault_class"] == "Normal Operation")
        ].head(10)

    if farm_records.empty:
        return None, None

    current_tel = telemetry_dict.get(current_rec["record_id"])
    target_len = len(current_tel) if current_tel is not None else WINDOW_STEPS

    aligned_matrices = [
        telemetry_dict[rid][SIGNAL_NAMES].values
        for rid in farm_records["record_id"]
        if rid in telemetry_dict and len(telemetry_dict[rid]) == target_len
    ]
    if not aligned_matrices:
        return None, None

    stacked = np.stack(aligned_matrices, axis=0)
    mean_mat = np.mean(stacked, axis=0)
    std_mat = np.std(stacked, axis=0)

    idx = (
        current_tel.index
        if current_tel is not None
        else pd.date_range(start=current_rec["start_time"], periods=target_len, freq="10min", tz="UTC")
    )

    mean_df = pd.DataFrame(mean_mat, index=idx, columns=SIGNAL_NAMES)
    std_df = pd.DataFrame(std_mat, index=idx, columns=SIGNAL_NAMES)
    return mean_df, std_df


def main():
    """Main Streamlit execution function for SCADA Data Inspection Visualizer."""
    try:
        st.set_page_config(
            page_title="SCADA Data Inspection Visualizer",
            page_icon="🔍",
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass

    # Custom styling
    st.markdown(
        """
        <style>
            .stMetric { background-color: var(--secondary-background-color); padding: 12px; border-radius: 8px; border: 1px solid rgba(128, 128, 128, 0.15); }
            .event-badge { display: inline-block; padding: 4px 12px; border-radius: 14px; font-weight: 700; font-size: 0.85rem; }
            .annotation-card { background-color: var(--secondary-background-color); border-radius: 8px; padding: 16px; margin-bottom: 12px; border: 1px solid rgba(128, 128, 128, 0.2); }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Load unified data
    df_all_records, telemetry_dict = load_all_wind_farms()

    # ------------------ SIDEBAR CONTROLS ------------------
    st.sidebar.title("🔍 SCADA Data Inspection")
    st.sidebar.caption("Penmanshiel & Kelmarsh Wind Fleets | 20 Turbines")
    st.sidebar.markdown("---")

    # 1. Wind Farm & Turbine Selection
    st.sidebar.subheader("1. Asset Selection")
    farm_filter = st.sidebar.radio(
        "Wind Farm:",
        ["All Wind Farms (20 Turbines)", "Penmanshiel (14 Turbines)", "Kelmarsh (6 Turbines)"],
        index=0,
    )

    if "Penmanshiel" in farm_filter:
        farm_records = df_all_records[df_all_records["wind_farm"] == "Penmanshiel"]
    elif "Kelmarsh" in farm_filter:
        farm_records = df_all_records[df_all_records["wind_farm"] == "Kelmarsh"]
    else:
        farm_records = df_all_records

    available_turbines = sorted(farm_records["turbine_id"].unique().tolist())
    selected_turbine_a = st.sidebar.selectbox(
        "Primary Wind Turbine (Asset A):",
        available_turbines,
        index=0,
    )

    turb_a_records = farm_records[farm_records["turbine_id"] == selected_turbine_a].sort_values("start_time")

    # 2. Date and Time Selection
    st.sidebar.markdown("---")
    st.sidebar.subheader("2. Date & Time Selection")

    # Filter by operational state
    state_filter = st.sidebar.selectbox(
        "Filter by Operational State:",
        ["All Records", "Normal Operation Only", "Fault / Anomaly Events Only"],
        index=0,
    )
    if state_filter == "Normal Operation Only":
        filtered_records = turb_a_records[turb_a_records["fault_class"] == "Normal Operation"]
    elif state_filter == "Fault / Anomaly Events Only":
        filtered_records = turb_a_records[turb_a_records["fault_class"] != "Normal Operation"]
    else:
        filtered_records = turb_a_records

    if filtered_records.empty:
        st.sidebar.warning("No records match the current operational filter. Reverting to all records.")
        filtered_records = turb_a_records

    # Calendar Date Picker
    min_date = filtered_records["start_time"].min().date()
    max_date = filtered_records["start_time"].max().date()

    picked_date = st.sidebar.date_input(
        "Select Date (UTC):",
        value=min_date,
        min_value=min_date,
        max_value=max_date,
    )

    # Records on or closest to picked date
    records_on_date = filtered_records[filtered_records["start_time"].dt.date == picked_date]
    if records_on_date.empty:
        # Snap to closest record
        time_diffs = (filtered_records["start_time"].dt.date - picked_date).abs()
        closest_date = filtered_records.loc[time_diffs.idxmin(), "start_time"].date()
        records_on_date = filtered_records[filtered_records["start_time"].dt.date == closest_date]
        st.sidebar.info(f"Showing nearest active date: **{closest_date}**")

    # Stepper buttons
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5 = st.sidebar.columns(5)
    all_record_ids = filtered_records["record_id"].tolist()
    curr_idx = st.session_state.get("inspection_idx", 0)
    if curr_idx >= len(all_record_ids):
        curr_idx = 0

    with nav_col1:
        if st.button("⏮️", help="First record"):
            curr_idx = 0
            st.session_state["inspection_idx"] = curr_idx
    with nav_col2:
        if st.button("◀️", help="Previous record"):
            curr_idx = max(0, curr_idx - 1)
            st.session_state["inspection_idx"] = curr_idx
    with nav_col3:
        if st.button("🎲", help="Random record"):
            import random
            curr_idx = random.randint(0, len(all_record_ids) - 1)
            st.session_state["inspection_idx"] = curr_idx
    with nav_col4:
        if st.button("▶️", help="Next record"):
            curr_idx = min(len(all_record_ids) - 1, curr_idx + 1)
            st.session_state["inspection_idx"] = curr_idx
    with nav_col5:
        if st.button("⏭️", help="Last record"):
            curr_idx = len(all_record_ids) - 1
            st.session_state["inspection_idx"] = curr_idx

    # Record / Timeframe selector
    selected_record_id = st.sidebar.selectbox(
        "Available Time Windows:",
        all_record_ids,
        index=curr_idx,
        format_func=lambda rid: (
            f"{filtered_records.loc[filtered_records['record_id'] == rid, 'start_time'].dt.strftime('%Y-%m-%d %H:%M').values[0]} UTC "
            f"[{filtered_records.loc[filtered_records['record_id'] == rid, 'fault_class'].values[0]}]"
        ),
    )
    st.session_state["inspection_idx"] = all_record_ids.index(selected_record_id)

    # 3. Channel & Units Controls
    st.sidebar.markdown("---")
    st.sidebar.subheader("3. Signal & Display Options")
    unit_mode = st.sidebar.radio(
        "Sensor Units:",
        ["Engineering Units", "Normalized (Z-Score)", "Min-Max Normalized [0, 1]"],
        index=0,
    )
    visible_signals = st.sidebar.multiselect(
        "Active SCADA Channels:",
        SIGNAL_NAMES,
        default=SIGNAL_NAMES,
    )
    if not visible_signals:
        visible_signals = SIGNAL_NAMES

    # Get active record & telemetry
    rec_row = filtered_records[filtered_records["record_id"] == selected_record_id].iloc[0]
    telemetry_df = telemetry_dict[selected_record_id]

    # Process annotations
    annotation_info = parse_event_annotations(rec_row, telemetry_df)
    fault_color = FAULT_COLOR_MAP.get(rec_row["fault_class"], "#3B82F6")
    fault_icon = FAULT_ICONS.get(rec_row["fault_class"], "📌")

    # ------------------ MAIN HEADER ------------------
    st.title("🔍 SCADA Telemetry & Operational Data Inspection")

    # Top Status Bar
    header_col1, header_col2, header_col3 = st.columns([1.2, 1.2, 1.0])
    with header_col1:
        st.markdown(
            f"""
            <div class="annotation-card" style="border-left: 5px solid {fault_color};">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: gray; font-weight: 700;">Selected Asset & Site</div>
                <div style="font-size: 1.2rem; font-weight: 800; color: #1E293B;">🌪️ {rec_row['turbine_id']}</div>
                <div style="font-size: 0.8rem; color: gray;">{rec_row['wind_farm']} Wind Farm &middot; {rec_row['turbine_model']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_col2:
        st.markdown(
            f"""
            <div class="annotation-card" style="border-left: 5px solid #3B82F6;">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: gray; font-weight: 700;">Monitored Timeframe Window</div>
                <div style="font-size: 1.15rem; font-weight: 700;">🕒 {rec_row['start_time'].strftime('%Y-%m-%d %H:%M')} &rarr; {rec_row['end_time'].strftime('%H:%M UTC')}</div>
                <div style="font-size: 0.8rem; color: gray;">Duration: <b>12.0 Hours</b> &middot; 72 Steps @ 10-min Res</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with header_col3:
        st.markdown(
            f"""
            <div class="annotation-card" style="border-left: 5px solid {fault_color};">
                <div style="font-size: 0.75rem; text-transform: uppercase; color: gray; font-weight: 700;">SCADA Event Annotation</div>
                <div style="font-size: 1.15rem; font-weight: 800; color: {fault_color};">{fault_icon} {rec_row['fault_class']}</div>
                <div style="font-size: 0.8rem; color: gray;">Ground-Truth Operational Label</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ------------------ TABS ------------------
    tab_telemetry, tab_annotations, tab_turb_comp, tab_baseline, tab_export = st.tabs(
        [
            "📈 SCADA Telemetry Curves",
            "🚨 SCADA Event Annotations & Alarms",
            "🔄 Turbine-to-Turbine Comparison",
            "⚖️ Baseline Benchmarking",
            "💾 Raw Telemetry & Export",
        ]
    )

    # ==================== TAB 1: SCADA TELEMETRY CURVES ====================
    with tab_telemetry:
        st.subheader("📈 Multi-Channel Sensor Telemetry")

        plot_df = telemetry_df.copy()
        if unit_mode == "Normalized (Z-Score)":
            plot_df = (plot_df - plot_df.mean()) / (plot_df.std() + 1e-6)
        elif unit_mode == "Min-Max Normalized [0, 1]":
            plot_df = (plot_df - plot_df.min()) / (plot_df.max() - plot_df.min() + 1e-6)

        layout_mode = st.radio(
            "Visualization Layout:",
            ["Subsystem Grouped (3 Panels)", "Stacked (All Selected Channels)", "Unified Overlay"],
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

            # Aero
            for col_name, color in [("wind_speed", "#3B82F6"), ("power", "#10B981"), ("pitch_angle", "#8B5CF6")]:
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

            # Mech
            for col_name, color in [("rotor_speed", "#F59E0B"), ("generator_rpm", "#EC4899"), ("drivetrain_accel", "#EF4444")]:
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

            # Thermal
            for col_name, color in [("gear_oil_temp", "#DC2626"), ("gen_bearing_temp", "#D97706")]:
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

            # Add threshold reference lines if in engineering units
            if unit_mode == "Engineering Units":
                if "gear_oil_temp" in visible_signals:
                    fig_sync.add_hline(
                        y=SIGNAL_THRESHOLDS["gear_oil_temp"]["warning"],
                        line_dash="dot",
                        line_color="rgba(239, 68, 68, 0.6)",
                        annotation_text="Gear Oil Warn (65°C)",
                        row=3,
                        col=1,
                    )
                if "gen_bearing_temp" in visible_signals:
                    fig_sync.add_hline(
                        y=SIGNAL_THRESHOLDS["gen_bearing_temp"]["warning"],
                        line_dash="dot",
                        line_color="rgba(217, 119, 6, 0.6)",
                        annotation_text="Bearing Warn (70°C)",
                        row=3,
                        col=1,
                    )

            fig_sync.update_layout(
                height=720,
                margin={"l": 30, "r": 20, "t": 40, "b": 30},
                hovermode="x unified",
            )
            st.plotly_chart(fig_sync, use_container_width=True)

        elif layout_mode == "Stacked (All Selected Channels)":
            channels_to_plot = [c for c in visible_signals if c in plot_df]
            fig_stack = make_subplots(
                rows=len(channels_to_plot),
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=[f"{c} ({SIGNAL_META[c].unit})" for c in channels_to_plot],
            )
            for i, c in enumerate(channels_to_plot):
                fig_stack.add_trace(
                    go.Scatter(x=plot_df.index, y=plot_df[c], name=c, line={"width": 2}),
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
                        go.Scatter(x=plot_df.index, y=plot_df[c], name=f"{c} ({SIGNAL_META[c].unit})", line={"width": 2})
                    )
            fig_ov.update_layout(
                height=480,
                margin={"l": 30, "r": 20, "t": 30, "b": 30},
                hovermode="x unified",
                title=f"Overlay Telemetry: {selected_record_id} ({rec_row['turbine_id']})",
            )
            st.plotly_chart(fig_ov, use_container_width=True)

        # Statistical Metrics Table
        st.markdown("#### 📐 SCADA Sensor Window Statistics")
        stats_rows = []
        for c in visible_signals:
            if c in telemetry_df:
                series = telemetry_df[c]
                start_v = float(series.iloc[0])
                end_v = float(series.iloc[-1])
                delta_v = end_v - start_v
                stats_rows.append(
                    {
                        "Channel": c,
                        "Unit": SIGNAL_META[c].unit,
                        "Mean": round(float(series.mean()), 2),
                        "Std Dev": round(float(series.std()), 2),
                        "Min": round(float(series.min()), 2),
                        "Median": round(float(series.median()), 2),
                        "Max": round(float(series.max()), 2),
                        "Start": round(start_v, 2),
                        "End": round(end_v, 2),
                        "Delta": f"{delta_v:+.2f}",
                    }
                )
        st.dataframe(pd.DataFrame(stats_rows), use_container_width=True, hide_index=True)

    # ==================== TAB 2: SCADA EVENT ANNOTATIONS & ALARMS ====================
    with tab_annotations:
        st.subheader("🚨 SCADA Event Annotations & Alarms")

        col_ev1, col_ev2 = st.columns([1.2, 0.8])

        with col_ev1:
            st.markdown("#### 📋 Operational Event Summary & Diagnostics")
            st.markdown(
                f"""
                <div style="background-color: var(--secondary-background-color); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 18px; margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                        <span style="font-size: 1.1rem; font-weight: 700; color: {fault_color};">{fault_icon} {annotation_info['fault_class']}</span>
                        <span class="event-badge" style="background-color: {fault_color}22; color: {fault_color};">SCADA Annotation</span>
                    </div>
                    <p style="font-size: 0.95rem; line-height: 1.5; color: var(--text-color);">
                        <b>Engineering Rationale:</b><br>{annotation_info['rationale'] or "Turbine telemetry stayed within nominal design thresholds over the monitored period."}
                    </p>
                    <div style="margin-top: 12px; padding: 10px; background-color: rgba(16, 185, 129, 0.1); border-left: 3px solid #10B981; border-radius: 4px;">
                        <b>Recommended Action:</b><br>{annotation_info['action']}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_ev2:
            st.markdown("#### 🔔 SCADA Alarm Event Log")
            alarm_df = pd.DataFrame(annotation_info["alarms"])
            st.dataframe(alarm_df, use_container_width=True, hide_index=True)

        # Alarm Timeline Chart
        st.markdown("#### ⏱️ Sensor Anomaly Timeline & Threshold Reference")
        fig_alarm_time = go.Figure()
        fig_alarm_time.add_trace(
            go.Scatter(
                x=telemetry_df.index,
                y=telemetry_df["wind_speed"],
                name="Wind Speed (m/s)",
                line={"color": "#3B82F6", "width": 2},
            )
        )
        fig_alarm_time.add_trace(
            go.Scatter(
                x=telemetry_df.index,
                y=telemetry_df["power"] / 100.0,
                name="Power (kW / 100)",
                line={"color": "#10B981", "width": 2},
            )
        )
        if rec_row["fault_class"] == "Gearbox Overheating":
            fig_alarm_time.add_trace(
                go.Scatter(
                    x=telemetry_df.index,
                    y=telemetry_df["gear_oil_temp"],
                    name="Gear Oil Temp (°C)",
                    line={"color": "#EF4444", "width": 2.5},
                )
            )
            fig_alarm_time.add_hline(y=65.0, line_dash="dash", line_color="red", annotation_text="65°C Threshold")
        elif rec_row["fault_class"] == "Generator Bearing Anomaly":
            fig_alarm_time.add_trace(
                go.Scatter(
                    x=telemetry_df.index,
                    y=telemetry_df["gen_bearing_temp"],
                    name="Bearing Temp (°C)",
                    line={"color": "#F59E0B", "width": 2.5},
                )
            )
            fig_alarm_time.add_hline(y=70.0, line_dash="dash", line_color="orange", annotation_text="70°C Threshold")
        elif rec_row["fault_class"] == "Pitch / Aerodynamic Fault":
            fig_alarm_time.add_trace(
                go.Scatter(
                    x=telemetry_df.index,
                    y=telemetry_df["pitch_angle"],
                    name="Pitch Angle (°)",
                    line={"color": "#8B5CF6", "width": 2},
                )
            )
            fig_alarm_time.add_trace(
                go.Scatter(
                    x=telemetry_df.index,
                    y=telemetry_df["drivetrain_accel"] / 10.0,
                    name="Vibration (mm/s² / 10)",
                    line={"color": "#EF4444", "width": 2},
                )
            )

        fig_alarm_time.update_layout(
            height=340,
            margin={"l": 20, "r": 20, "t": 30, "b": 20},
            hovermode="x unified",
            title="SCADA Operational Timeline with Event Cross-Section",
        )
        st.plotly_chart(fig_alarm_time, use_container_width=True)

    # ==================== TAB 3: TURBINE-TO-TURBINE COMPARISON ====================
    with tab_turb_comp:
        st.subheader("🔄 Turbine-to-Turbine SCADA Comparison")
        st.caption(
            "Compare the primary wind turbine against another turbine to evaluate cross-asset divergence, "
            "localized wake effects, or mechanical degradation."
        )

        col_comp_ctrl1, col_comp_ctrl2, col_comp_ctrl3 = st.columns([1.0, 1.0, 1.0])
        all_turbines_list = sorted(df_all_records["turbine_id"].unique().tolist())
        comp_candidates = [t for t in all_turbines_list if t != selected_turbine_a]

        with col_comp_ctrl1:
            selected_turbine_b = st.selectbox(
                "Comparison Wind Turbine (Asset B):",
                comp_candidates,
                index=0,
            )

        with col_comp_ctrl2:
            match_mode = st.radio(
                "Comparison Alignment:",
                ["Concurrent Timestamp (Same Time)", "Custom Window"],
                horizontal=True,
            )

        # Locate Turbine B record
        if match_mode == "Concurrent Timestamp (Same Time)":
            sister_rid = find_concurrent_sister_window(df_all_records, rec_row, selected_turbine_b)
            if sister_rid is None:
                sister_rid = df_all_records[df_all_records["turbine_id"] == selected_turbine_b]["record_id"].iloc[0]
        else:
            sister_candidates = df_all_records[df_all_records["turbine_id"] == selected_turbine_b]
            sister_rid = st.selectbox(
                "Select Asset B Window:",
                sister_candidates["record_id"].tolist(),
                format_func=lambda rid: (
                    f"{sister_candidates.loc[sister_candidates['record_id'] == rid, 'start_time'].dt.strftime('%Y-%m-%d %H:%M').values[0]} UTC "
                    f"[{sister_candidates.loc[sister_candidates['record_id'] == rid, 'fault_class'].values[0]}]"
                ),
            )

        rec_b = df_all_records[df_all_records["record_id"] == sister_rid].iloc[0]
        telemetry_b = telemetry_dict[sister_rid]

        with col_comp_ctrl3:
            comp_signal = st.selectbox("Primary Signal to Compare:", visible_signals, index=0)

        # Asset comparison banner
        b_color = FAULT_COLOR_MAP.get(rec_b["fault_class"], "#64748B")
        st.info(
            f"Comparing **{selected_turbine_a}** (`{selected_record_id}`, {rec_row['fault_class']}) "
            f"vs **{selected_turbine_b}** (`{sister_rid}`, {rec_b['fault_class']}) "
            f"&middot; Asset B Time: `{rec_b['start_time'].strftime('%Y-%m-%d %H:%M')} UTC`"
        )

        # Overlay & Residual Subplots
        sig_a_vals = telemetry_df[comp_signal].values
        sig_b_vals = telemetry_b[comp_signal].values
        residual_ab = sig_a_vals - sig_b_vals
        time_axis = telemetry_df.index

        fig_comp = make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.65, 0.35],
            subplot_titles=[
                f"Dual Turbine Trajectory: {comp_signal} ({SIGNAL_META[comp_signal].unit})",
                f"Residual Difference Δ ({selected_turbine_a} minus {selected_turbine_b})",
            ],
        )

        # Turbine A trace
        fig_comp.add_trace(
            go.Scatter(
                x=time_axis,
                y=sig_a_vals,
                name=f"{selected_turbine_a} (Asset A)",
                line={"color": fault_color, "width": 2.5},
            ),
            row=1,
            col=1,
        )

        # Turbine B trace
        fig_comp.add_trace(
            go.Scatter(
                x=time_axis,
                y=sig_b_vals,
                name=f"{selected_turbine_b} (Asset B)",
                line={"color": "#64748B", "width": 2, "dash": "dash"},
            ),
            row=1,
            col=1,
        )

        # Residual Bar trace
        fig_comp.add_trace(
            go.Bar(
                x=time_axis,
                y=residual_ab,
                name="Residual (A - B)",
                marker={"color": np.where(residual_ab >= 0, "rgba(239, 68, 68, 0.6)", "rgba(59, 130, 246, 0.6)")},
            ),
            row=2,
            col=1,
        )

        fig_comp.update_layout(
            height=540,
            margin={"l": 30, "r": 20, "t": 40, "b": 30},
            hovermode="x unified",
        )
        st.plotly_chart(fig_comp, use_container_width=True)

        # Side-by-side Comparative Metrics
        st.markdown("#### 📊 Asset A vs Asset B Channel Statistics")
        comp_rows = []
        for c in visible_signals:
            if c in telemetry_df and c in telemetry_b:
                val_a = telemetry_df[c].values
                val_b = telemetry_b[c].values
                mean_a = float(np.mean(val_a))
                mean_b = float(np.mean(val_b))
                max_a = float(np.max(val_a))
                max_b = float(np.max(val_b))
                diff_mean = mean_a - mean_b
                comp_rows.append(
                    {
                        "Signal": c,
                        "Unit": SIGNAL_META[c].unit,
                        f"{selected_turbine_a} Mean": round(mean_a, 2),
                        f"{selected_turbine_b} Mean": round(mean_b, 2),
                        "Mean Delta (A - B)": f"{diff_mean:+.2f}",
                        f"{selected_turbine_a} Max": round(max_a, 2),
                        f"{selected_turbine_b} Max": round(max_b, 2),
                    }
                )
        st.dataframe(pd.DataFrame(comp_rows), use_container_width=True, hide_index=True)

        # Cross-turbine Correlation Scatter
        st.markdown(f"#### 🔍 Cross-Asset Correlation: {comp_signal}")
        fig_corr_scatter = px.scatter(
            x=sig_b_vals,
            y=sig_a_vals,
            labels={"x": f"{selected_turbine_b} ({SIGNAL_META[comp_signal].unit})", "y": f"{selected_turbine_a} ({SIGNAL_META[comp_signal].unit})"},
            title=f"Correlation Scatter: {selected_turbine_a} vs {selected_turbine_b} ({comp_signal})",
            trendline="ols",
        )
        fig_corr_scatter.update_layout(height=360, margin={"l": 20, "r": 20, "t": 30, "b": 20})
        st.plotly_chart(fig_corr_scatter, use_container_width=True)

    # ==================== TAB 4: BASELINE BENCHMARKING ====================
    with tab_baseline:
        st.subheader("⚖️ Baseline SCADA Benchmarking")
        st.caption("Compare the active telemetry window against healthy nominal operating standards.")

        baseline_type = st.radio(
            "Select Benchmark Baseline:",
            [
                "1. Matched Healthy Window (Same/Sister Asset)",
                "2. Farm Fleet Average Baseline (Concurrent Sister Assets)",
                "3. Manufacturer Theoretical IEC Power Curve (Senvion 2.05 MW)",
            ],
            index=0,
            horizontal=False,
        )

        col_base_sig1, col_base_sig2 = st.columns([1.0, 1.0])
        with col_base_sig1:
            base_eval_signal = st.selectbox("Signal for Baseline Deviation:", visible_signals, index=0)

        if "1. Matched Healthy" in baseline_type:
            healthy_rid, healthy_df = find_matching_healthy_baseline(
                df_all_records, telemetry_dict, rec_row, telemetry_df
            )
            healthy_rec = df_all_records[df_all_records["record_id"] == healthy_rid].iloc[0]

            st.caption(
                f"**Matched Healthy Baseline Window:** `{healthy_rid}` ({healthy_rec['turbine_id']}) &middot; "
                f"Mean Wind Speed: `{healthy_df['wind_speed'].mean():.2f} m/s` (Current: `{telemetry_df['wind_speed'].mean():.2f} m/s`)"
            )

            cur_v = telemetry_df[base_eval_signal].values
            base_v = healthy_df[base_eval_signal].values
            res_v = cur_v - base_v
            t_axis = np.arange(len(cur_v)) * 10

            fig_base = make_subplots(
                rows=2,
                cols=1,
                shared_xaxes=True,
                row_heights=[0.65, 0.35],
                subplot_titles=[
                    f"Current Window vs Healthy Baseline ({base_eval_signal})",
                    "Residual Deviation (Current - Healthy Baseline)",
                ],
            )
            fig_base.add_trace(
                go.Scatter(x=t_axis, y=cur_v, name="Current Window", line={"color": fault_color, "width": 2.5}),
                row=1,
                col=1,
            )
            fig_base.add_trace(
                go.Scatter(x=t_axis, y=base_v, name=f"Healthy Baseline ({healthy_rid})", line={"color": "#10B981", "width": 2, "dash": "dash"}),
                row=1,
                col=1,
            )
            fig_base.add_trace(
                go.Bar(x=t_axis, y=res_v, name="Residual Deviation", marker={"color": "rgba(239, 68, 68, 0.5)"}),
                row=2,
                col=1,
            )
            fig_base.update_layout(height=480, hovermode="x unified", margin={"l": 20, "r": 20, "t": 30, "b": 20})
            st.plotly_chart(fig_base, use_container_width=True)

        elif "2. Farm Fleet Average" in baseline_type:
            mean_fleet_df, std_fleet_df = compute_fleet_average_baseline(df_all_records, telemetry_dict, rec_row)
            if mean_fleet_df is not None and base_eval_signal in mean_fleet_df:
                cur_v = telemetry_df[base_eval_signal].values
                fleet_mean = mean_fleet_df[base_eval_signal].values
                fleet_std = std_fleet_df[base_eval_signal].values if std_fleet_df is not None else np.zeros_like(fleet_mean)
                t_axis = telemetry_df.index

                fig_fleet = go.Figure()
                # Fleet envelope (+/- 2 std)
                upper_env = fleet_mean + 2 * fleet_std
                lower_env = np.maximum(0, fleet_mean - 2 * fleet_std)

                fig_fleet.add_trace(
                    go.Scatter(
                        x=t_axis,
                        y=upper_env,
                        mode="lines",
                        line={"width": 0},
                        showlegend=False,
                    )
                )
                fig_fleet.add_trace(
                    go.Scatter(
                        x=t_axis,
                        y=lower_env,
                        mode="lines",
                        line={"width": 0},
                        fill="tonexty",
                        fillcolor="rgba(148, 163, 184, 0.2)",
                        name="Fleet Norm Envelope (±2σ)",
                    )
                )
                fig_fleet.add_trace(
                    go.Scatter(
                        x=t_axis,
                        y=fleet_mean,
                        mode="lines",
                        name="Fleet Average Mean",
                        line={"color": "#10B981", "width": 2, "dash": "dash"},
                    )
                )
                fig_fleet.add_trace(
                    go.Scatter(
                        x=t_axis,
                        y=cur_v,
                        mode="lines+markers",
                        name=f"Current: {rec_row['turbine_id']}",
                        line={"color": fault_color, "width": 2.5},
                    )
                )
                fig_fleet.update_layout(
                    height=440,
                    margin={"l": 20, "r": 20, "t": 30, "b": 20},
                    hovermode="x unified",
                    title=f"Fleet Norm Envelope vs Active Asset ({base_eval_signal})",
                )
                st.plotly_chart(fig_fleet, use_container_width=True)
            else:
                st.warning("Insufficient concurrent sister turbine telemetry to calculate fleet average envelope.")

        else:
            # 3. Manufacturer Theoretical Power Curve
            ws_cur = telemetry_df["wind_speed"].values
            p_cur = telemetry_df["power"].values
            p_theo = compute_theoretical_power(ws_cur, model=rec_row["turbine_model"])
            p_loss = np.maximum(0, p_theo - p_cur)
            total_loss_kwh = float(np.sum(p_loss) * (10.0 / 60.0))  # 10 min steps

            b_m1, b_m2, b_m3 = st.columns(3)
            with b_m1:
                st.metric("Actual Generation", f"{np.sum(p_cur) * (10 / 60):,.1f} kWh")
            with b_m2:
                st.metric("Theoretical Yield", f"{np.sum(p_theo) * (10 / 60):,.1f} kWh")
            with b_m3:
                st.metric("Curtailed / Lost Generation", f"{total_loss_kwh:,.1f} kWh", delta=f"-{total_loss_kwh:,.0f} kWh", delta_color="inverse")

            ws_ref = np.linspace(0, 25, 200)
            p_ref = compute_theoretical_power(ws_ref, model=rec_row["turbine_model"])

            fig_theo = go.Figure()
            fig_theo.add_trace(
                go.Scatter(x=ws_ref, y=p_ref, mode="lines", name=f"Manufacturer Specification ({rec_row['turbine_model']})", line={"color": "#1E293B", "width": 3, "dash": "dash"})
            )
            fig_theo.add_trace(
                go.Scatter(
                    x=ws_cur,
                    y=p_cur,
                    mode="markers",
                    name=f"Observed SCADA Data ({rec_row['fault_class']})",
                    marker={"size": 8, "color": fault_color},
                )
            )
            fig_theo.update_layout(
                xaxis_title="Hub Wind Speed (m/s)",
                yaxis_title="Electrical Active Power (kW)",
                height=420,
                margin={"l": 20, "r": 20, "t": 30, "b": 20},
                title="Actual SCADA Power Curve vs Manufacturer Model",
            )
            st.plotly_chart(fig_theo, use_container_width=True)

    # ==================== TAB 5: RAW TELEMETRY & EXPORT ====================
    with tab_export:
        st.subheader("💾 Raw Telemetry & Data Export")
        st.caption(f"Inspection table for record `{selected_record_id}` ({rec_row['turbine_id']}) with all 72 timesteps.")

        st.dataframe(telemetry_df, use_container_width=True)

        csv_data = telemetry_df.to_csv().encode("utf-8")
        st.download_button(
            label=f"📥 Download SCADA Window CSV ({selected_record_id})",
            data=csv_data,
            file_name=f"scada_{selected_record_id}_{rec_row['turbine_id'].replace(' ', '_')}.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
