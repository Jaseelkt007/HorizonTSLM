"""Interactive Streamlit dashboard to inspect and understand Kelmarsh SCADA dataset and TimeNet benchmarks."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Dynamically locate repository root (containing pyproject.toml)
_curr = Path(__file__).resolve().parent
while not (_curr / "pyproject.toml").exists() and _curr.parent != _curr:
    _curr = _curr.parent
REPO_ROOT = _curr

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.schemas import (
    FAULT_CLASSES,
    SELECTED_SIGNALS,
    SIGNAL_NAMES,
    WINDOW_STEPS,
    SignalSpec,
)

# Colors for fault classes
FAULT_COLOR_MAP = {
    "Normal Operation": "#10B981",              # Emerald green
    "Gearbox Overheating": "#EF4444",           # Crimson red
    "Generator Bearing Anomaly": "#F59E0B",     # Amber orange
    "Pitch / Aerodynamic Fault": "#8B5CF6",     # Purple
    "Turbine Trip / Forced Outage": "#EC4899",  # Pink
}

SIGNAL_META = {s.canonical_name: s for s in SELECTED_SIGNALS}


@st.cache_data(show_spinner="Loading Kelmarsh Wind Farm static specifications...")
def load_static_metadata() -> pd.DataFrame:
    """Load turbine static geographic and technical specifications."""
    static_path = REPO_ROOT / "data" / "kelmarsh" / "Kelmarsh_WT_static.csv"
    if static_path.exists():
        df = pd.read_csv(static_path)
        return df
    return pd.DataFrame()


@st.cache_data(show_spinner="Loading and caching TimeNet SCADA telemetry...")
def load_timenet_dataset() -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """Load records and 8-channel signals from TimeNet local registry or fallback cache."""
    from timenet.client import TimeNet
    from timenet.registry.factory import default_registry_path

    client = TimeNet(registry=default_registry_path())
    dataset = client.load("energy/kelmarsh-wind-scada")

    records_list = []
    telemetry_dict = {}

    for r in dataset.records:
        rec_id = r.record_id
        rec_data: Dict[str, Any] = {
            "record_id": rec_id,
            "start_time_us": r.start_time,
            "start_time": pd.to_datetime(r.start_time, unit="us", utc=True),
        }
        for a in r.annotations:
            if a.key == "turbine_id":
                rec_data["turbine_id"] = a.value
            elif a.key == "fault_class":
                rec_data["fault_class"] = a.value
            elif a.key == "wind_farm":
                rec_data["wind_farm"] = a.value

        # Extract tasks
        tasks = [t for t in dataset.tasks if rec_id in t.record_ids]
        for t in tasks:
            if type(t).__name__ == "AnswerTask":
                rec_data["prompt"] = getattr(t, "prompt", "")
                rec_data["target"] = getattr(t, "target", "")
                rec_data["rationale"] = getattr(t, "rationale", "")

        # End time = start_time + 72 * 10 minutes
        rec_data["end_time"] = rec_data["start_time"] + pd.Timedelta(minutes=10 * WINDOW_STEPS)

        # Extract time series signals
        sig_map = {}
        for ts in r.time_series:
            sig_map[ts.signal] = ts.to_numpy()

        # Build individual window dataframe
        timestamps = pd.date_range(
            start=rec_data["start_time"],
            periods=WINDOW_STEPS,
            freq="10min",
            tz="UTC",
        )
        df_sig = pd.DataFrame(sig_map, index=timestamps)
        df_sig.index.name = "timestamp"

        telemetry_dict[rec_id] = df_sig
        records_list.append(rec_data)

    df_records = pd.DataFrame(records_list)
    return df_records, telemetry_dict


def compute_theoretical_power(wind_speeds: np.ndarray) -> np.ndarray:
    """Compute theoretical Senvion MM92 power curve (rated 2050 kW)."""
    cut_in = 3.0
    rated_speed = 12.5
    cut_out = 25.0
    rated_power = 2050.0

    p = np.zeros_like(wind_speeds, dtype=float)
    valid_mask = (wind_speeds >= cut_in) & (wind_speeds < rated_speed)
    p[valid_mask] = rated_power * ((wind_speeds[valid_mask] - cut_in) / (rated_speed - cut_in)) ** 3
    p[(wind_speeds >= rated_speed) & (wind_speeds <= cut_out)] = rated_power
    p[wind_speeds > cut_out] = 0.0
    return np.clip(p, 0.0, rated_power)


def main():
    st.set_page_config(
        page_title="Kelmarsh Wind SCADA - Dataset Inspector",
        page_icon="🌪️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Custom styling
    st.markdown(
        """
        <style>
        .metric-card {
            background-color: var(--secondary-background-color);
            border: 1px solid rgba(128, 128, 128, 0.2);
            border-radius: 8px;
            padding: 14px 18px;
            margin-bottom: 12px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 16px;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 1.05rem;
            font-weight: 500;
        }
        .cot-box {
            background-color: rgba(99, 102, 241, 0.08);
            border-left: 4px solid #6366F1;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
            font-size: 0.95rem;
        }
        .action-box {
            background-color: rgba(16, 185, 129, 0.08);
            border-left: 4px solid #10B981;
            padding: 12px 16px;
            border-radius: 4px;
            margin: 8px 0;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Load data
    try:
        df_records, telemetry_dict = load_timenet_dataset()
        df_static = load_static_metadata()
    except Exception as e:
        st.error(f"Error loading TimeNet dataset: {e}")
        st.info("Ensure the dataset is registered via `uv run python scripts/build_timenet.py`.")
        return

    # ------------------ SIDEBAR ------------------
    st.sidebar.image("https://img.icons8.com/fluency/96/wind-turbine.png", width=64)
    st.sidebar.title("Kelmarsh SCADA")
    st.sidebar.caption("Zurich Hackathon Time-Series Inspector")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Dataset Filters")

    # Turbine selection
    turbine_list = ["All Turbines"] + sorted(df_records["turbine_id"].unique().tolist())
    selected_turbine = st.sidebar.selectbox("Turbine Filter", turbine_list, index=0)

    # Fault class selection
    fault_classes = ["All Categories"] + sorted(df_records["fault_class"].unique().tolist())
    selected_fault = st.sidebar.selectbox("Diagnosis / Fault Category", fault_classes, index=0)

    # Filter dataframe
    filtered_df = df_records.copy()
    if selected_turbine != "All Turbines":
        filtered_df = filtered_df[filtered_df["turbine_id"] == selected_turbine]
    if selected_fault != "All Categories":
        filtered_df = filtered_df[filtered_df["fault_class"] == selected_fault]

    st.sidebar.info(f"Showing **{len(filtered_df)}** of **{len(df_records)}** telemetry windows.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Select Window")

    if filtered_df.empty:
        st.warning("No records match current filter criteria.")
        return

    window_ids = filtered_df["record_id"].tolist()

    # Quick navigation
    col_nav1, col_nav2 = st.sidebar.columns(2)
    with col_nav1:
        if st.button("⬅️ Previous", use_container_width=True):
            curr_idx = st.session_state.get("selected_win_idx", 0)
            st.session_state["selected_win_idx"] = max(0, curr_idx - 1)
    with col_nav2:
        if st.button("Next ➡️", use_container_width=True):
            curr_idx = st.session_state.get("selected_win_idx", 0)
            st.session_state["selected_win_idx"] = min(len(window_ids) - 1, curr_idx + 1)

    selected_win_idx = st.session_state.get("selected_win_idx", 0)
    if selected_win_idx >= len(window_ids):
        selected_win_idx = 0

    selected_record_id = st.sidebar.selectbox(
        "Window ID",
        window_ids,
        index=selected_win_idx,
        format_func=lambda rid: f"{rid} ({filtered_df.loc[filtered_df['record_id']==rid, 'fault_class'].values[0]})",
    )
    # Sync state
    st.session_state["selected_win_idx"] = window_ids.index(selected_record_id)

    st.sidebar.markdown("---")
    st.sidebar.subheader("Display Options")
    unit_mode = st.sidebar.radio(
        "Signal Scaling",
        ["Physical Units", "Normalized (Z-Score)", "Min-Max Normalized [0, 1]"],
        index=0,
    )

    selected_signals_sidebar = st.sidebar.multiselect(
        "Visible Channels",
        SIGNAL_NAMES,
        default=SIGNAL_NAMES,
        format_func=lambda s: f"{s} ({SIGNAL_META[s].unit})",
    )

    # ------------------ MAIN CONTENT ------------------
    st.title("🌪️ Kelmarsh Wind Farm SCADA Telemetry Inspector")
    st.caption("Standardized TimeNet Benchmark (`energy/kelmarsh-wind-scada`) | 12-Hour Windows | 8 Continuous Sensors")

    # Tabs
    tab_fleet, tab_window, tab_power, tab_compare, tab_data = st.tabs([
        "🛰️ Fleet & Farm Overview",
        "📈 Telemetry Window Inspector",
        "🌪️ Power Curve & Analytics",
        "⚖️ Anomaly Comparison",
        "💾 Raw Data & Export",
    ])

    # ==================== TAB 1: FLEET & FARM OVERVIEW ====================
    with tab_fleet:
        st.subheader("Kelmarsh Wind Farm Summary & Asset Distribution")

        # Metrics row
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.metric("Total Windows", f"{len(df_records):,}")
        with m2:
            st.metric("Fleet Assets", f"{df_records['turbine_id'].nunique()} Turbines")
        with m3:
            st.metric("Continuous Signals", f"{len(SIGNAL_NAMES)} Channels")
        with m4:
            st.metric("Window Duration", "12 Hours (72 pts)")
        with m5:
            st.metric("Total Monitored Time", f"{len(df_records) * 12:,} Hours")
        with m6:
            anomaly_cnt = len(df_records[df_records["fault_class"] != "Normal Operation"])
            st.metric("Fault Windows", f"{anomaly_cnt} ({anomaly_cnt / len(df_records) * 100:.1f}%)")

        col_map, col_dist = st.columns([1.1, 1.0])

        with col_map:
            st.markdown("#### 📍 Turbine Geographic Layout (Northamptonshire, UK)")
            if not df_static.empty and "Latitude" in df_static.columns and "Longitude" in df_static.columns:
                fig_map = px.scatter(
                    df_static,
                    x="Longitude",
                    y="Latitude",
                    hover_name="Title",
                    text="Title",
                    size="Rated power (kW)",
                    color="Hub Height (m)",
                    color_continuous_scale="Viridis",
                    labels={"Hub Height (m)": "Hub Ht (m)"},
                    title="Kelmarsh Wind Turbines (Senvion MM92 - 2.05 MW each)",
                )
                fig_map.update_traces(textposition="top center", marker=dict(size=18, line=dict(width=2, color="DarkSlateGrey")))
                fig_map.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=380)
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.info("Geographic coordinates not available in static metadata.")

        with col_dist:
            st.markdown("#### 🏷️ Diagnostic Class Breakdown by Turbine")
            ct = pd.crosstab(df_records["turbine_id"], df_records["fault_class"])
            fig_bar = px.bar(
                ct.reset_index(),
                x="turbine_id",
                y=list(ct.columns),
                title="Telemetry Windows per Fault Class by Turbine",
                labels={"value": "Window Count", "turbine_id": "Turbine"},
                color_discrete_map=FAULT_COLOR_MAP,
                barmode="stack",
            )
            fig_bar.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=380, legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5))
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 📋 Sensor Channels & Taxonomy Specifications")
        spec_rows = []
        for s in SELECTED_SIGNALS:
            spec_rows.append({
                "Canonical Name": s.canonical_name,
                "Description": s.description,
                "Unit": s.unit,
                "Greenbyte ID": s.greenbyte_id,
                "CSV Column Prefix": s.csv_column_prefix,
                "Min Threshold": s.min_val,
                "Max Threshold": s.max_val,
            })
        st.dataframe(pd.DataFrame(spec_rows), use_container_width=True, hide_index=True)

    # ==================== TAB 2: TELEMETRY WINDOW INSPECTOR ====================
    with tab_window:
        rec_row = df_records[df_records["record_id"] == selected_record_id].iloc[0]
        cur_telemetry = telemetry_dict[selected_record_id]

        # Header card
        status_color = FAULT_COLOR_MAP.get(rec_row["fault_class"], "#6B7280")
        st.markdown(
            f"""
            <div style="background-color: var(--secondary-background-color); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 16px; margin-bottom: 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h3 style="margin: 0;">Telemetry Window: <code>{selected_record_id}</code></h3>
                        <p style="margin: 4px 0 0 0; color: gray;">
                            Asset: <b>{rec_row['turbine_id']}</b> &nbsp;|&nbsp; 
                            Timespan: <b>{rec_row['start_time'].strftime('%Y-%m-%d %H:%M')}</b> to <b>{rec_row['end_time'].strftime('%Y-%m-%d %H:%M')} UTC</b> (12 Hours)
                        </p>
                    </div>
                    <div>
                        <span style="background-color: {status_color}; color: white; padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 0.95rem;">
                            {rec_row['fault_class']}
                        </span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # AI Chain-of-Thought & Maintenance Card
        st.markdown("#### 🧠 Supervisory Diagnostic Task & Chain-of-Thought Reasoning")
        if rec_row.get("prompt"):
            st.markdown(f"**Prompt:** *\"{rec_row['prompt']}\"*")

        col_cot, col_act = st.columns([1.2, 0.8])
        with col_cot:
            st.markdown(
                f"""
                <div class="cot-box">
                    <b style="color: #4F46E5;">🔍 Physical Chain-of-Thought Rationale:</b><br/>
                    {rec_row.get('rationale', 'No rationale provided.')}
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col_act:
            st.markdown(
                f"""
                <div class="action-box">
                    <b style="color: #059669;">🛠️ Recommended Action / Target:</b><br/>
                    {rec_row.get('target', 'No action target.')}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("---")
        st.markdown("#### 📊 Multi-Sensor Telemetry Time-Series")

        # Signal scaling
        plot_df = cur_telemetry.copy()
        if unit_mode == "Normalized (Z-Score)":
            plot_df = (plot_df - plot_df.mean()) / (plot_df.std() + 1e-6)
        elif unit_mode == "Min-Max Normalized [0, 1]":
            plot_df = (plot_df - plot_df.min()) / (plot_df.max() - plot_df.min() + 1e-6)

        # Signal grouping
        view_mode = st.radio(
            "Visualization Layout",
            ["Subsystem Grouped (3 Panels)", "Stacked All Channels", "Single Overlay"],
            horizontal=True,
        )

        if view_mode == "Subsystem Grouped (3 Panels)":
            fig_sync = make_subplots(
                rows=3,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                subplot_titles=[
                    "🌬️ Aerodynamics & Generation (Wind Speed, Power, Blade Pitch)",
                    "⚙️ Mechanical Drive Train (Rotor RPM, Generator RPM, Vibration)",
                    "🌡️ Thermal Monitoring (Gear Oil Temp, Bearing Temp)",
                ],
            )

            # Panel 1: Aero
            for col_name, color in [("wind_speed", "#3B82F6"), ("power", "#10B981"), ("pitch_angle", "#8B5CF6")]:
                if col_name in selected_signals_sidebar and col_name in plot_df:
                    fig_sync.add_trace(
                        go.Scatter(x=plot_df.index, y=plot_df[col_name], name=f"{col_name} ({SIGNAL_META[col_name].unit})", line=dict(color=color, width=2)),
                        row=1, col=1,
                    )

            # Panel 2: Mechanical
            for col_name, color in [("rotor_speed", "#F59E0B"), ("generator_rpm", "#EC4899"), ("drivetrain_accel", "#EF4444")]:
                if col_name in selected_signals_sidebar and col_name in plot_df:
                    fig_sync.add_trace(
                        go.Scatter(x=plot_df.index, y=plot_df[col_name], name=f"{col_name} ({SIGNAL_META[col_name].unit})", line=dict(color=color, width=2)),
                        row=2, col=1,
                    )

            # Panel 3: Thermal
            for col_name, color in [("gear_oil_temp", "#DC2626"), ("gen_bearing_temp", "#D97706")]:
                if col_name in selected_signals_sidebar and col_name in plot_df:
                    fig_sync.add_trace(
                        go.Scatter(x=plot_df.index, y=plot_df[col_name], name=f"{col_name} ({SIGNAL_META[col_name].unit})", line=dict(color=color, width=2)),
                        row=3, col=1,
                    )

            fig_sync.update_layout(height=750, margin=dict(l=30, r=20, t=50, b=30), hovermode="x unified")
            st.plotly_chart(fig_sync, use_container_width=True)

        elif view_mode == "Stacked All Channels":
            active_channels = [c for c in selected_signals_sidebar if c in plot_df]
            fig_stack = make_subplots(
                rows=len(active_channels),
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.03,
                subplot_titles=[f"{c} ({SIGNAL_META[c].unit})" for c in active_channels],
            )
            for i, c in enumerate(active_channels):
                fig_stack.add_trace(
                    go.Scatter(x=plot_df.index, y=plot_df[c], name=c, line=dict(width=2)),
                    row=i + 1, col=1,
                )
            fig_stack.update_layout(height=180 * len(active_channels), margin=dict(l=30, r=20, t=40, b=30), hovermode="x unified")
            st.plotly_chart(fig_stack, use_container_width=True)

        else:
            fig_ov = go.Figure()
            for c in selected_signals_sidebar:
                if c in plot_df:
                    fig_ov.add_trace(go.Scatter(x=plot_df.index, y=plot_df[c], name=f"{c} ({SIGNAL_META[c].unit})", line=dict(width=2)))
            fig_ov.update_layout(height=480, margin=dict(l=30, r=20, t=40, b=30), hovermode="x unified", title="All Selected Signals Overlay")
            st.plotly_chart(fig_ov, use_container_width=True)

        # Window Statistics Table
        st.markdown("#### 📐 Window Statistical Metrics")
        stats_df = cur_telemetry[selected_signals_sidebar].describe().T[["mean", "std", "min", "50%", "max"]]
        stats_df.columns = ["Mean", "Std Dev", "Min", "Median", "Max"]
        stats_df["Unit"] = [SIGNAL_META[idx].unit for idx in stats_df.index]
        stats_df["Description"] = [SIGNAL_META[idx].description for idx in stats_df.index]
        st.dataframe(stats_df.round(2), use_container_width=True)

    # ==================== TAB 3: POWER CURVE & ANALYTICS ====================
    with tab_power:
        st.subheader("🌪️ Turbine Analytics & Aerodynamic Power Curves")
        st.write("Evaluating aerodynamic efficiency, power generation dynamics, and mechanical relationships.")

        col_pc_opt1, col_pc_opt2 = st.columns([1, 2])
        with col_pc_opt1:
            curve_scope = st.radio(
                "Data Scope for Power Curve",
                ["Current Selected Window (72 pts)", "Filtered Subset", "All 180 Windows (12,960 pts)"],
                index=1,
            )

        # Gather points
        if curve_scope == "Current Selected Window (72 pts)":
            scatter_dfs = [cur_telemetry.assign(fault_class=rec_row["fault_class"], turbine_id=rec_row["turbine_id"])]
        elif curve_scope == "Filtered Subset":
            scatter_dfs = [telemetry_dict[rid].assign(fault_class=df_records.loc[df_records["record_id"]==rid, "fault_class"].values[0], turbine_id=df_records.loc[df_records["record_id"]==rid, "turbine_id"].values[0]) for rid in filtered_df["record_id"]]
        else:
            scatter_dfs = [telemetry_dict[rid].assign(fault_class=df_records.loc[df_records["record_id"]==rid, "fault_class"].values[0], turbine_id=df_records.loc[df_records["record_id"]==rid, "turbine_id"].values[0]) for rid in df_records["record_id"]]

        combined_scatter_df = pd.concat(scatter_dfs, ignore_index=True)

        col_curve, col_corr = st.columns([1.2, 0.8])

        with col_curve:
            st.markdown("#### Wind Speed vs Active Power Curve")
            ws_ref = np.linspace(0, 25, 200)
            p_ref = compute_theoretical_power(ws_ref)

            fig_power = px.scatter(
                combined_scatter_df,
                x="wind_speed",
                y="power",
                color="fault_class",
                color_discrete_map=FAULT_COLOR_MAP,
                opacity=0.6,
                labels={"wind_speed": "Wind Speed (m/s)", "power": "Active Electrical Power (kW)", "fault_class": "Fault Class"},
                title=f"SCADA Power Curve vs Senvion MM92 Theoretical Model (2050 kW)",
            )
            fig_power.add_trace(
                go.Scatter(
                    x=ws_ref,
                    y=p_ref,
                    mode="lines",
                    name="Senvion MM92 Theoretical Curve",
                    line=dict(color="#1E293B", width=3, dash="dash"),
                )
            )
            fig_power.update_layout(height=480, margin=dict(l=20, r=20, t=40, b=20), legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"))
            st.plotly_chart(fig_power, use_container_width=True)

        with col_corr:
            st.markdown("#### Sensor Cross-Correlation Matrix")
            corr_mat = combined_scatter_df[SIGNAL_NAMES].corr()
            fig_corr = px.imshow(
                corr_mat,
                text_auto=".2f",
                color_continuous_scale="RdBu_r",
                zmin=-1,
                zmax=1,
                title="Telemetry Correlation Heatmap",
            )
            fig_corr.update_layout(height=480, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_corr, use_container_width=True)

        # Cross-sensor scatter row
        st.markdown("---")
        st.markdown("#### ⚙️ Mechanical & Thermal Couplings")
        sc1, sc2 = st.columns(2)
        with sc1:
            fig_gear = px.scatter(
                combined_scatter_df,
                x="rotor_speed",
                y="generator_rpm",
                color="fault_class",
                color_discrete_map=FAULT_COLOR_MAP,
                title="Rotor RPM vs Generator RPM (Gearbox Transmission Ratio ~1:105)",
                labels={"rotor_speed": "Rotor RPM", "generator_rpm": "Generator RPM"},
                opacity=0.7,
            )
            fig_gear.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_gear, use_container_width=True)
        with sc2:
            fig_thermal = px.scatter(
                combined_scatter_df,
                x="gear_oil_temp",
                y="gen_bearing_temp",
                color="fault_class",
                color_discrete_map=FAULT_COLOR_MAP,
                title="Gear Oil Temperature vs Generator Bearing Temperature (°C)",
                labels={"gear_oil_temp": "Gear Oil Temp (°C)", "gen_bearing_temp": "Bearing Temp (°C)"},
                opacity=0.7,
            )
            fig_thermal.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_thermal, use_container_width=True)

    # ==================== TAB 4: ANOMALY COMPARISON ====================
    with tab_compare:
        st.subheader("⚖️ Anomaly vs Baseline Normal Operation")
        st.write("Compare the current window against a normal operating baseline window to isolate anomaly signatures.")

        normal_records = df_records[df_records["fault_class"] == "Normal Operation"]
        same_turb_normals = normal_records[normal_records["turbine_id"] == rec_row["turbine_id"]]
        baseline_candidates = same_turb_normals if not same_turb_normals.empty else normal_records

        baseline_rec_id = st.selectbox(
            "Select Normal Baseline Window",
            baseline_candidates["record_id"].tolist(),
            format_func=lambda rid: f"{rid} ({df_records.loc[df_records['record_id']==rid, 'turbine_id'].values[0]} - Normal Operation)",
        )

        baseline_df = telemetry_dict[baseline_rec_id]
        comp_signal = st.selectbox("Signal to Compare", SIGNAL_NAMES, index=0)

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.metric(
                f"Selected Window ({rec_row['fault_class']}) - Mean",
                f"{cur_telemetry[comp_signal].mean():.2f} {SIGNAL_META[comp_signal].unit}",
            )
        with col_c2:
            st.metric(
                f"Baseline Window (Normal Operation) - Mean",
                f"{baseline_df[comp_signal].mean():.2f} {SIGNAL_META[comp_signal].unit}",
                delta=f"{cur_telemetry[comp_signal].mean() - baseline_df[comp_signal].mean():+.2f} {SIGNAL_META[comp_signal].unit}",
                delta_color="inverse",
            )

        steps = np.arange(WINDOW_STEPS) * 10
        fig_comp = go.Figure()
        fig_comp.add_trace(
            go.Scatter(
                x=steps,
                y=cur_telemetry[comp_signal].values,
                name=f"Current: {selected_record_id} ({rec_row['fault_class']})",
                line=dict(color=FAULT_COLOR_MAP.get(rec_row["fault_class"], "#EF4444"), width=2.5),
            )
        )
        fig_comp.add_trace(
            go.Scatter(
                x=steps,
                y=baseline_df[comp_signal].values,
                name=f"Baseline: {baseline_rec_id} (Normal)",
                line=dict(color="#10B981", width=2, dash="dash"),
            )
        )

        delta_vals = cur_telemetry[comp_signal].values - baseline_df[comp_signal].values
        fig_comp.add_trace(
            go.Bar(
                x=steps,
                y=delta_vals,
                name="Residual (Current - Baseline)",
                marker=dict(color="rgba(148, 163, 184, 0.4)"),
            )
        )

        fig_comp.update_layout(
            title=f"12-Hour Trajectory Comparison: {SIGNAL_META[comp_signal].description} ({SIGNAL_META[comp_signal].unit})",
            xaxis_title="Elapsed Time (Minutes)",
            yaxis_title=f"{comp_signal} ({SIGNAL_META[comp_signal].unit})",
            height=480,
            hovermode="x unified",
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_comp, use_container_width=True)

    # ==================== TAB 5: RAW DATA & EXPORT ====================
    with tab_data:
        st.subheader("💾 Raw Telemetry Matrix & TimeNet Metadata")

        col_d1, col_d2 = st.columns([1, 1])
        with col_d1:
            st.markdown(f"#### Window Matrix: `{selected_record_id}` (72 timesteps × 8 sensors)")
            st.dataframe(cur_telemetry, use_container_width=True)

            csv_win = cur_telemetry.to_csv().encode("utf-8")
            st.download_button(
                label=f"📥 Download Window {selected_record_id} as CSV",
                data=csv_win,
                file_name=f"kelmarsh_{selected_record_id}_telemetry.csv",
                mime="text/csv",
            )

        with col_d2:
            st.markdown("#### TimeNet Annotations & Metadata Record")
            st.json(
                {
                    "record_id": rec_row["record_id"],
                    "turbine_id": rec_row["turbine_id"],
                    "fault_class": rec_row["fault_class"],
                    "start_time": str(rec_row["start_time"]),
                    "end_time": str(rec_row["end_time"]),
                    "sampling_frequency": "10 minutes (RegularAxis)",
                    "steps": WINDOW_STEPS,
                    "prompt": rec_row.get("prompt"),
                    "target": rec_row.get("target"),
                    "rationale": rec_row.get("rationale"),
                }
            )


if __name__ == "__main__":
    main()
