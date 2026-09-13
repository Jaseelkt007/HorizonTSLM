"""SCADA data preprocessor: signal extraction, status alignment, window slicing, and CoT generation."""

import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from mk.src.data.schemas import (
        FAULT_CLASS_TO_IDX,
        FAULT_CLASSES,
        HIGH_FREQUENCY_CODE_MAP,
        IEC_CATEGORY_MAP,
        IDX_TO_FAULT_CLASS,
        IDX_TO_SUBSYSTEM_CLASS,
        IDX_TO_TRIAGE_CLASS,
        KELMARSH_TURBINES,
        PENMANSHIEL_TURBINES,
        SELECTED_SIGNALS,
        SERVICE_CONTRACT_CATEGORY_MAP,
        SIGNAL_NAMES,
        SUBSYSTEM_CLASS_TO_IDX,
        SUBSYSTEM_CLASSES,
        SUBSYSTEM_TO_COARSE_FAULT,
        TRIAGE_CLASS_TO_IDX,
        TRIAGE_CLASSES,
        WINDOW_STEPS,
        StatusEventRecord,
        StructuredLMTarget,
    )
except ImportError:
    from src.data.schemas import (
        FAULT_CLASS_TO_IDX,
        FAULT_CLASSES,
        HIGH_FREQUENCY_CODE_MAP,
        IEC_CATEGORY_MAP,
        IDX_TO_FAULT_CLASS,
        IDX_TO_SUBSYSTEM_CLASS,
        IDX_TO_TRIAGE_CLASS,
        KELMARSH_TURBINES,
        PENMANSHIEL_TURBINES,
        SELECTED_SIGNALS,
        SERVICE_CONTRACT_CATEGORY_MAP,
        SIGNAL_NAMES,
        SUBSYSTEM_CLASS_TO_IDX,
        SUBSYSTEM_CLASSES,
        SUBSYSTEM_TO_COARSE_FAULT,
        TRIAGE_CLASS_TO_IDX,
        TRIAGE_CLASSES,
        WINDOW_STEPS,
        StatusEventRecord,
        StructuredLMTarget,
    )



@dataclass
class TelemetryWindow:
    turbine_id: str
    start_time: str
    end_time: str
    signals: np.ndarray  # shape: (WINDOW_STEPS, num_channels)
    channel_names: list[str]
    label_idx: int
    label_name: str
    prompt: str
    rationale: str
    action: str
    status_events: list[dict[str, Any]]
    structured_target: StructuredLMTarget | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "turbine_id": self.turbine_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "signals": self.signals.tolist(),
            "channel_names": self.channel_names,
            "label_idx": self.label_idx,
            "label_name": self.label_name,
            "prompt": self.prompt,
            "rationale": self.rationale,
            "action": self.action,
            "status_events": self.status_events,
        }
        if self.structured_target is not None:
            d["structured_target"] = self.structured_target.to_formatted_target()
        return d


def parse_greenbyte_csv(filepath: Path) -> pd.DataFrame:
    """Parse Greenbyte exported CSV by skipping leading comment lines, properly detecting header."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header_line_idx = None
    for idx, line in enumerate(lines):
        clean = line.lstrip("#").strip()
        if not clean:
            continue
        # Check for header indicators in SCADA telemetry or Status logs
        if (
            clean.startswith("Date and time")
            or clean.startswith("Timestamp")
            or clean.startswith("Date/time")
            or clean.startswith("DateTime")
            or (not line.startswith("#") and line.strip() and "," in line)
        ):
            header_line_idx = idx
            break

    if header_line_idx is None:
        raise ValueError(f"No valid data rows found in {filepath}")

    df = pd.read_csv(
        filepath,
        skiprows=header_line_idx,
        low_memory=False,
        encoding="utf-8",
        on_bad_lines="skip",
    )
    # Clean column names: strip any leading '#' and whitespace
    df.columns = [c.lstrip("#").strip() for c in df.columns]
    return df


def extract_scada_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DatetimeIndex]:
    """Identify and extract the 8 selected continuous channels from raw SCADA df with intelligent fallbacks."""
    # First column is timestamp
    time_col = df.columns[0]
    timestamps = pd.to_datetime(df[time_col], utc=True)

    extracted = pd.DataFrame(index=timestamps)

    for sig in SELECTED_SIGNALS:
        matched_col = None
        for col in df.columns:
            if col.startswith(sig.csv_column_prefix):
                # Prefer exact match or non-min/max/std column
                if "Max" not in col and "Min" not in col and "Std" not in col and "Standard" not in col:
                    matched_col = col
                    break
                elif matched_col is None:
                    matched_col = col

        if matched_col is not None:
            # Use .to_numpy() to prevent pandas index misalignment between RangeIndex and DatetimeIndex
            extracted[sig.canonical_name] = pd.to_numeric(df[matched_col], errors="coerce").to_numpy()
        else:
            # Fallback if specific signal not present in this export
            extracted[sig.canonical_name] = np.nan

    # Fallback checks for missing channels in older exports (e.g. 2016-2018 Penmanshiel)
    # 1. Gear oil temperature fallback: check inlet temperature, gearbox temp, or stator temp
    if extracted["gear_oil_temp"].isna().all() or (extracted["gear_oil_temp"] == 0.0).all():
        for alt in ["Gear oil inlet temperature", "Gearbox temperature", "Stator temperature 1", "Stator temperature"]:
            alt_col = next((c for c in df.columns if c.startswith(alt) and "Max" not in c and "Min" not in c and "Std" not in c), None)
            if alt_col is not None:
                vals = pd.to_numeric(df[alt_col], errors="coerce").to_numpy()
                if not np.isnan(vals).all() and not (vals == 0.0).all():
                    extracted["gear_oil_temp"] = vals
                    break

    # 2. Pitch angle fallbacks: Blade A primary, B and C filled from available alternatives
    for pitch_col, alts in [
        ("pitch_angle_a", ["Blade angle (pitch position) B", "Blade angle (pitch position) C", "Pitch angle"]),
        ("pitch_angle_b", ["Blade angle (pitch position) A", "Blade angle (pitch position) C", "Pitch angle"]),
        ("pitch_angle_c", ["Blade angle (pitch position) A", "Blade angle (pitch position) B", "Pitch angle"]),
    ]:
        if extracted[pitch_col].isna().all() or (extracted[pitch_col] == 0.0).all():
            found = False
            for alt in alts:
                alt_col = next((c for c in df.columns if c.startswith(alt) and "Max" not in c and "Min" not in c and "Std" not in c), None)
                if alt_col is not None:
                    vals = pd.to_numeric(df[alt_col], errors="coerce").to_numpy()
                    if not np.isnan(vals).all() and not (vals == 0.0).all():
                        extracted[pitch_col] = vals
                        found = True
                        break
            if not found:
                # Aerodynamic control curve estimate
                w = extracted["wind_speed"].to_numpy()
                p = extracted["power"].to_numpy()
                est_pitch = np.where(w > 12.0, (w - 12.0) * 3.5, 0.5)
                est_pitch = np.where((w > 4.0) & (p < 5.0), 88.0, est_pitch)
                extracted[pitch_col] = est_pitch

    # 3. Ambient temperature fallback: use nacelle interior or a constant 12°C if unavailable
    if "ambient_temp" in extracted.columns and (extracted["ambient_temp"].isna().all() or (extracted["ambient_temp"] == 0.0).all()):
        for alt in ["Nacelle temperature", "Ambient temperature (converter)"]:
            alt_col = next((c for c in df.columns if c.startswith(alt) and "Max" not in c and "Min" not in c and "Std" not in c), None)
            if alt_col is not None:
                vals = pd.to_numeric(df[alt_col], errors="coerce").to_numpy()
                if not np.isnan(vals).all():
                    extracted["ambient_temp"] = vals
                    break
        else:
            extracted["ambient_temp"] = 12.0  # temperate-climate default

    # Forward fill missing values then backward fill
    extracted = extracted.ffill().bfill().fillna(0.0)

    # Sort chronologically
    extracted = extracted.sort_index()
    return extracted, extracted.index


def _parse_duration_seconds(val: Any, default_seconds: float = 0.0) -> float:
    """Parse duration value into float seconds handling numeric, HH:MM:SS, and DD:HH:MM:SS formats."""
    if val is None or pd.isna(val):
        return default_seconds
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s == "-":
        return default_seconds
    try:
        return float(s)
    except ValueError:
        pass
    parts = s.split(":")
    if len(parts) == 3:  # HH:MM:SS
        try:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except ValueError:
            pass
    elif len(parts) == 4:  # DD:HH:MM:SS
        try:
            return float(parts[0]) * 86400 + float(parts[1]) * 3600 + float(parts[2]) * 60 + float(parts[3])
        except ValueError:
            pass
    return default_seconds


def parse_status_events(status_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Parse status log rows into timestamped event dictionaries including contractual and IEC categories."""
    events = []
    start_col = [c for c in status_df.columns if "start" in c.lower()]
    end_col = [c for c in status_df.columns if "end" in c.lower()]
    dur_col = [c for c in status_df.columns if "duration" in c.lower()]
    msg_col = [c for c in status_df.columns if "message" in c.lower()]
    code_col = [c for c in status_df.columns if "code" in c.lower()]
    status_type_col = [c for c in status_df.columns if c.strip().lower() == "status"]
    svc_col = [c for c in status_df.columns if "service" in c.lower()]
    iec_col = [c for c in status_df.columns if "iec" in c.lower()]
    comm_col = [c for c in status_df.columns if "comment" in c.lower()]
    glob_col = [c for c in status_df.columns if "global" in c.lower()]
    cust_col = [c for c in status_df.columns if "custom" in c.lower()]

    if not start_col:
        return events

    s_col = start_col[0]
    e_col = end_col[0] if end_col else s_col
    d_col = dur_col[0] if dur_col else None
    m_col = msg_col[0] if msg_col else "Message"
    c_col = code_col[0] if code_col else "Code"
    st_col = status_type_col[0] if status_type_col else "Status"
    sv_col = svc_col[0] if svc_col else None
    ic_col = iec_col[0] if iec_col else None
    cm_col = comm_col[0] if comm_col else None
    gl_col = glob_col[0] if glob_col else None
    cu_col = cust_col[0] if cust_col else None

    for _, row in status_df.iterrows():
        try:
            start_t = pd.to_datetime(row[s_col], utc=True)
            end_t = pd.to_datetime(row[e_col], utc=True) if pd.notna(row.get(e_col)) else start_t
            if pd.isna(start_t):
                continue

            fallback_dur = (end_t - start_t).total_seconds() if end_t >= start_t else 0.0
            duration_val = fallback_dur
            if d_col and pd.notna(row.get(d_col)):
                duration_val = _parse_duration_seconds(row[d_col], default_seconds=fallback_dur)

            svc_val = str(row.get(sv_col, "")) if sv_col and pd.notna(row.get(sv_col)) else ""
            iec_val = str(row.get(ic_col, "")) if ic_col and pd.notna(row.get(ic_col)) else ""
            comm_val = str(row.get(cm_col, "")) if cm_col and pd.notna(row.get(cm_col)) else ""
            gl_val = str(row.get(gl_col, "")) if gl_col and pd.notna(row.get(gl_col)) else ""
            cu_val = str(row.get(cu_col, "")) if cu_col and pd.notna(row.get(cu_col)) else ""

            events.append(
                {
                    "start": start_t,
                    "end": end_t,
                    "duration": duration_val,
                    "status": str(row.get(st_col, "")).strip(),
                    "code": str(row.get(c_col, "")).strip(),
                    "message": str(row.get(m_col, "")).strip(),
                    "service_contract_category": svc_val.strip(),
                    "iec_category": iec_val.strip(),
                    "comment": comm_val.strip(),
                    "global_contract_category": gl_val.strip(),
                    "custom_contract_category": cu_val.strip(),
                }
            )
        except Exception:
            continue

    return events



@dataclass
class EventClassificationResult:
    """Rich ground truth classification result for a telemetry window.

    Supports tuple unpacking (label_idx, label_name = result) for backward compatibility
    with existing models, dataloaders, and tests.
    """

    label_idx: int
    label_name: str
    subsystem: str
    subsystem_idx: int
    triage: str
    triage_idx: int
    severity: str
    matched_events: list[dict[str, Any]]
    telemetry_flags: dict[str, Any]

    def __iter__(self):
        yield self.label_idx
        yield self.label_name

    def __getitem__(self, index: int):
        if index == 0:
            return self.label_idx
        elif index == 1:
            return self.label_name
        raise IndexError("EventClassificationResult index out of range (use attributes for extended metadata)")

    def __len__(self) -> int:
        return 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_idx": self.label_idx,
            "label_name": self.label_name,
            "subsystem": self.subsystem,
            "subsystem_idx": self.subsystem_idx,
            "triage": self.triage,
            "triage_idx": self.triage_idx,
            "severity": self.severity,
            "num_matched_events": len(self.matched_events),
            "telemetry_flags": self.telemetry_flags,
        }


# Canonical Subsystem Rules mapped from taxonomy.yaml & problem-statement.md section 8
SUBSYSTEM_RULES: list[dict[str, Any]] = [
    {
        "subsystem": "generator_cooling",
        "kind": "fault",
        "coarse_fault": "Generator Bearing Anomaly",
        "patterns": [
            "overload generator fan",
            "overload generator heating",
            "overload transf. fan",
            "overload transformer fan",
            "generator cooling",
            "generator fan",
            "fan overload",
            "inlet air",
            "cooling air",
        ],
    },
    {
        "subsystem": "generator_bearing",
        "kind": "fault",
        "coarse_fault": "Generator Bearing Anomaly",
        "patterns": [
            "generator bearing",
            "bearing front temperature",
            "bearing rear temperature",
            "bearing temperature trip",
            "bearing temperature warning",
            "drive-end bearing",
            "non-drive-end bearing",
            "generator bearing anomaly",
            "front bearing",
            "rear bearing",
            "bearing 1",
            "bearing 2",
        ],
    },
    {
        "subsystem": "brake_hydraulics",
        "kind": "fault",
        "coarse_fault": "Turbine Trip / Forced Outage",
        "patterns": [
            "brake accumulator",
            "timeout brake",
            "feedback brake",
            "brake pads",
            "brake resistor",
            "hydraulic oil flushing",
            "low hydraulic pressure",
            "hydraulic pressure",
            "max. operation time hydraulic",
            "brake defect",
            "mechanical brake",
            "hydraulic pump",
        ],
    },
    {
        "subsystem": "pitch_system",
        "kind": "fault",
        "coarse_fault": "Pitch / Aerodynamic Fault",
        "patterns": [
            "battery charge cycle axis",
            "pitch measuring",
            "limit switch error",
            "lubrication pump pitch",
            "pitch batteries",
            "pitch controller",
            "temperature motor axis",
            "pitch angle",
            "pitch error",
            "pitch symmetry",
            "blade angle",
            "axis 1",
            "axis 2",
            "axis 3",
            "pitch position",
        ],
    },
    {
        "subsystem": "converter_grid",
        "kind": "fault",
        "coarse_fault": "Turbine Trip / Forced Outage",
        "patterns": [
            "frequency converter",
            "grid loss",
            "overvoltage",
            "grid frequency",
            "repeating error bp",
            "converter torque",
            "conv. generator speed",
            "grid current",
            "grid voltage",
            "converter error",
            "grid trip",
            "line voltage",
            "inverter",
        ],
    },
    {
        "subsystem": "gearbox_lubrication",
        "kind": "fault",
        "coarse_fault": "Gearbox Overheating",
        "patterns": [
            "gearbox oil",
            "gear oil",
            "missing gear oil",
            "gear bypass filter",
            "implausible gear speed",
            "particle sensor",
            "oil filter gear",
            "gear bearing",
            "gearbox temperature",
            "gear oil temperature",
            "gear oil pump",
            "gear oil pressure",
            "gearbox speed",
            "metal particle",
        ],
    },
    {
        "subsystem": "structural_overspeed",
        "kind": "fault",
        "coarse_fault": "Pitch / Aerodynamic Fault",
        "patterns": [
            "tower oscillation",
            "oscillation encoder",
            "high rotor speed",
            "max. acceleration",
            "tower resonance",
            "drivetrain oscillation",
            "drive train monitor",
            "extreme gust",
            "drivetrain acceleration",
            "rotor overspeed",
            "tower acceleration",
            "nacelle vibration",
        ],
    },
    {
        "subsystem": "yaw_cable",
        "kind": "fault",
        "coarse_fault": "Turbine Trip / Forced Outage",
        "patterns": [
            "cable autounwind",
            "manual yaw",
            "deviation winddirection",
            "yaw motor",
            "yaw speed",
            "cable twist",
            "yaw bearing",
            "yaw error",
        ],
    },
    {
        "subsystem": "sensor_comms",
        "kind": "fault",
        "coarse_fault": "Turbine Trip / Forced Outage",
        "patterns": [
            "comm. failure",
            "communication unavailable",
            "4-20",
            "vane 2 defect",
            "pmu",
            "time synchronization",
            "rotor sensor",
            "anemometer defect",
            "sensor fault",
            "fpm",
        ],
    },
    {
        "subsystem": "environmental_stop",
        "kind": "benign",
        "coarse_fault": "Normal Operation",
        "patterns": [
            "wind < start wind",
            "max. wind speed",
            "absence of wind",
            "warm-up",
            "ice",
            "icing",
            "low wind",
            "storm shutdown",
            "ambient temperature low",
        ],
    },
    {
        "subsystem": "curtailment_external",
        "kind": "benign",
        "coarse_fault": "Normal Operation",
        "patterns": [
            "externally stopped",
            "p output externally reduced",
            "reduced power converter",
            "curtailment",
            "grid request",
            "remote power limitation",
        ],
    },
    {
        "subsystem": "manual_safety",
        "kind": "context",
        "coarse_fault": "Turbine Trip / Forced Outage",
        "patterns": [
            "manual stop",
            "park master stop",
            "remote stop",
            "safety chain",
            "emergency stop",
            "battery test",
            "test brake program",
            "manual brake",
            "service switch",
        ],
    },
]


def check_telemetry_anomalies(signals_arr: np.ndarray | None) -> dict[str, Any]:
    """Inspect continuous SCADA telemetry for physical threshold excursions."""
    flags = {
        "high_gear_oil_temp": False,
        "high_gen_bearing_temp": False,
        "high_vibration": False,
        "power_trip": False,
        "high_pitch_asymmetry": False,
        "max_gear_oil_temp": 0.0,
        "max_gen_bearing_temp": 0.0,
        "max_vibe": 0.0,
        "gear_temp_delta": 0.0,
        "max_pitch_spread": 0.0,
        "ambient_temp": 12.0,
        "gear_oil_over_ambient": 0.0,
    }
    if signals_arr is None or signals_arr.size == 0 or signals_arr.shape[-1] < 8:
        return flags

    # Channels: 0:wind, 1:power, 2:rotor, 3:gen_rpm, 4:gear_oil, 5:gen_bearing,
    #           6:pitch_a, 7:pitch_b, 8:pitch_c, 9:vibe, 10:ambient_temp
    n_ch = signals_arr.shape[-1]
    wind = signals_arr[:, 0]
    power = signals_arr[:, 1]
    gear_oil = signals_arr[:, 4]
    gen_bearing = signals_arr[:, 5]
    pitch_a = signals_arr[:, 6]
    # Use channels 7/8 if present (11-channel), else fall back to pitch_a
    pitch_b = signals_arr[:, 7] if n_ch > 7 else pitch_a
    pitch_c = signals_arr[:, 8] if n_ch > 8 else pitch_a
    vibe = signals_arr[:, 9] if n_ch > 9 else signals_arr[:, 7]
    ambient = signals_arr[:, 10] if n_ch > 10 else np.full_like(gear_oil, 12.0)

    flags["max_gear_oil_temp"] = float(np.nanmax(gear_oil))
    flags["max_gen_bearing_temp"] = float(np.nanmax(gen_bearing))
    flags["max_vibe"] = float(np.nanmax(vibe))
    flags["gear_temp_delta"] = float(gear_oil[-1] - gear_oil[0])
    flags["ambient_temp"] = float(np.nanmean(ambient))

    # Thermal anomaly thresholds adjusted relative to ambient (removes seasonal aliasing)
    ambient_mean = flags["ambient_temp"]
    gear_over_ambient = flags["max_gear_oil_temp"] - ambient_mean
    flags["gear_oil_over_ambient"] = gear_over_ambient

    if flags["max_gear_oil_temp"] > 65.0 or flags["gear_temp_delta"] > 18.0 or gear_over_ambient > 52.0:
        flags["high_gear_oil_temp"] = True
    if flags["max_gen_bearing_temp"] > 70.0:
        flags["high_gen_bearing_temp"] = True
    if flags["max_vibe"] > 120.0:
        flags["high_vibration"] = True

    # Inter-blade pitch asymmetry: max spread across A/B/C blades at each timestep
    pitch_stack = np.stack([pitch_a, pitch_b, pitch_c], axis=0)  # (3, T)
    pitch_spread = np.nanmax(pitch_stack, axis=0) - np.nanmin(pitch_stack, axis=0)  # (T,)
    max_spread = float(np.nanmax(pitch_spread))
    flags["max_pitch_spread"] = max_spread
    if max_spread > 5.0:  # >5° inter-blade divergence is abnormal
        flags["high_pitch_asymmetry"] = True

    # Detect power collapse: wind > 4 m/s while power < 5 kW and pitch_a > 75 deg in trailing steps
    if len(wind) >= 6:
        if np.nanmean(wind[-6:]) > 4.0 and np.nanmean(power[-6:]) < 5.0 and np.nanmean(pitch_a[-6:]) > 75.0:
            if np.nanmax(power[: max(1, len(power) // 2)]) > 100.0:  # previously generating
                flags["power_trip"] = True

    return flags


def classify_window_events(
    events_in_window: list[dict[str, Any]] | None = None,
    signals_arr: np.ndarray | None = None,
    mode: str = "coarse",
    events: list[dict[str, Any]] | None = None,
) -> EventClassificationResult:
    """Classify a SCADA telemetry window into ground truth failure mode, subsystem, and triage categories.

    Parameters:
        events_in_window: List of status event dictionaries occurring in the window (or via events kwarg).
        signals_arr: Optional (N, 11) array of continuous telemetry channels.
        mode: Label space for primary (label_idx, label_name): "coarse" (5 classes) or "subsystem" (13 classes).
        events: Alias for events_in_window for flexible keyword invocation.

    Returns:
        EventClassificationResult with (label_idx, label_name) unpacking support, subsystem, triage, and severity.
    """
    if events_in_window is None:
        events_in_window = events if events is not None else []
    telemetry_flags = check_telemetry_anomalies(signals_arr)

    # 1. Handle windows with no event records
    if not events_in_window:
        if telemetry_flags.get("high_gear_oil_temp"):
            subsystem = "gearbox_lubrication"
            coarse_name = "Gearbox Overheating"
            triage = "fault"
            severity = "WARNING"
        elif telemetry_flags.get("high_gen_bearing_temp"):
            subsystem = "generator_bearing"
            coarse_name = "Generator Bearing Anomaly"
            triage = "fault"
            severity = "WARNING"
        elif telemetry_flags.get("high_vibration"):
            subsystem = "structural_overspeed"
            coarse_name = "Pitch / Aerodynamic Fault"
            triage = "fault"
            severity = "WARNING"
        elif telemetry_flags.get("high_pitch_asymmetry"):
            subsystem = "pitch_system"
            coarse_name = "Pitch / Aerodynamic Fault"
            triage = "fault"
            severity = "WARNING"
        elif telemetry_flags.get("power_trip"):
            subsystem = "manual_safety"
            coarse_name = "Turbine Trip / Forced Outage"
            triage = "fault"
            severity = "TRIP"
        else:
            subsystem = "normal_operation"
            coarse_name = "Normal Operation"
            triage = "normal"
            severity = "NOMINAL"

        label_name = coarse_name if mode == "coarse" else subsystem
        label_idx = FAULT_CLASS_TO_IDX[coarse_name] if mode == "coarse" else SUBSYSTEM_CLASS_TO_IDX[subsystem]

        return EventClassificationResult(
            label_idx=label_idx,
            label_name=label_name,
            subsystem=subsystem,
            subsystem_idx=SUBSYSTEM_CLASS_TO_IDX[subsystem],
            triage=triage,
            triage_idx=TRIAGE_CLASS_TO_IDX[triage],
            severity=severity,
            matched_events=[],
            telemetry_flags=telemetry_flags,
        )

    # 2. Evaluate all status events against empirical taxonomy maps and canonical subsystem rules
    matched_by_priority = []
    for ev in events_in_window:
        msg = str(ev.get("message", "")).lower()
        status = str(ev.get("status", "")).lower()
        code = str(ev.get("code", "")).strip()
        svc = str(ev.get("service_contract_category", "")).strip()
        iec = str(ev.get("iec_category", "")).strip()
        full_text = f"{msg} {code}"

        is_stop = "stop" in status or "trip" in status or "outage" in status or "emergency" in full_text
        if is_stop:
            ev_severity = "TRIP"
        elif "warning" in status or "alarm" in status:
            ev_severity = "WARNING"
        else:
            ev_severity = "INFO"

        # Tier 1: Subsystem rules (explicit text pattern matching on standardized message)
        pattern_matched = False
        for rule in SUBSYSTEM_RULES:
            if any(p in full_text for p in rule["patterns"]):
                matched_by_priority.append(
                    {
                        "subsystem": rule["subsystem"],
                        "kind": rule["kind"],
                        "coarse_fault": rule["coarse_fault"],
                        "severity": ev_severity,
                        "event": ev,
                        "is_stop": is_stop,
                        "source": "pattern_rule",
                    }
                )
                pattern_matched = True
                break

        if pattern_matched:
            continue

        # Tier 2: Exact code mapping (from data_structure_report.md Section 6)
        if code in HIGH_FREQUENCY_CODE_MAP:
            info = HIGH_FREQUENCY_CODE_MAP[code]
            rule_sev = "TRIP" if is_stop else info.get("severity", ev_severity)
            matched_by_priority.append(
                {
                    "subsystem": info["subsystem"],
                    "kind": "fault" if info["triage"] == "fault" else "benign",
                    "coarse_fault": info["coarse_fault"],
                    "severity": rule_sev,
                    "event": ev,
                    "is_stop": is_stop,
                    "source": "code_map",
                }
            )
            continue


        # Tier 3: Service Contract Category mapping (23 categories)
        if svc in SERVICE_CONTRACT_CATEGORY_MAP:
            info = SERVICE_CONTRACT_CATEGORY_MAP[svc]
            matched_by_priority.append(
                {
                    "subsystem": info["subsystem"],
                    "kind": "fault" if info["triage"] == "fault" else "benign",
                    "coarse_fault": info["coarse_fault"],
                    "severity": ev_severity,
                    "event": ev,
                    "is_stop": is_stop,
                    "source": "service_contract_map",
                }
            )
            continue

        # Tier 4: IEC Category mapping (8 classes)
        if iec in IEC_CATEGORY_MAP:
            info = IEC_CATEGORY_MAP[iec]
            matched_by_priority.append(
                {
                    "subsystem": info["subsystem"],
                    "kind": "fault" if info["triage"] == "fault" else "benign",
                    "coarse_fault": info["coarse_fault"],
                    "severity": ev_severity,
                    "event": ev,
                    "is_stop": is_stop,
                    "source": "iec_map",
                }
            )
            continue

    # 3. Fallback if none matched predefined patterns
    if not matched_by_priority:
        has_generic_stop = any(
            "stop" in str(ev.get("status", "")).lower() or "trip" in str(ev.get("message", "")).lower()
            for ev in events_in_window
        )
        if has_generic_stop or telemetry_flags.get("power_trip"):
            subsystem = "manual_safety"
            coarse_name = "Turbine Trip / Forced Outage"
            triage = "fault"
            severity = "TRIP"
        elif telemetry_flags.get("high_gear_oil_temp"):
            subsystem = "gearbox_lubrication"
            coarse_name = "Gearbox Overheating"
            triage = "fault"
            severity = "WARNING"
        elif telemetry_flags.get("high_gen_bearing_temp"):
            subsystem = "generator_bearing"
            coarse_name = "Generator Bearing Anomaly"
            triage = "fault"
            severity = "WARNING"
        elif telemetry_flags.get("high_vibration"):
            subsystem = "structural_overspeed"
            coarse_name = "Pitch / Aerodynamic Fault"
            triage = "fault"
            severity = "WARNING"
        else:
            subsystem = "normal_operation"
            coarse_name = "Normal Operation"
            triage = "normal"
            severity = "NOMINAL"

        label_name = coarse_name if mode == "coarse" else subsystem
        label_idx = FAULT_CLASS_TO_IDX[coarse_name] if mode == "coarse" else SUBSYSTEM_CLASS_TO_IDX[subsystem]

        return EventClassificationResult(
            label_idx=label_idx,
            label_name=label_name,
            subsystem=subsystem,
            subsystem_idx=SUBSYSTEM_CLASS_TO_IDX[subsystem],
            triage=triage,
            triage_idx=TRIAGE_CLASS_TO_IDX[triage],
            severity=severity,
            matched_events=[ev for ev in events_in_window],
            telemetry_flags=telemetry_flags,
        )

    # 4. Resolve multi-event windows using priority scoring
    def priority_score(m: dict[str, Any]) -> int:
        kind = m["kind"]
        sev = m["severity"]
        source_bonus = 5 if m.get("source") == "code_map" else 0
        if kind == "fault" and sev == "TRIP":
            return 100 + source_bonus
        if kind == "fault" and sev == "WARNING":
            return 90 + source_bonus
        if kind == "fault":
            return 80 + source_bonus
        if kind == "context" and sev == "TRIP":
            return 70 + source_bonus
        if kind == "benign" and sev == "TRIP":
            return 60 + source_bonus
        if kind == "benign":
            return 50 + source_bonus
        return 10 + source_bonus

    best_match = max(matched_by_priority, key=priority_score)
    subsystem = best_match["subsystem"]
    coarse_name = best_match["coarse_fault"]
    severity = best_match["severity"]

    if best_match["kind"] == "fault":
        triage = "fault"
    elif best_match["kind"] == "benign":
        triage = "benign_stop"
    else:
        triage = "benign_stop" if "test" in str(best_match["event"].get("message", "")).lower() else "fault"

    if telemetry_flags.get("power_trip") and severity != "TRIP":
        severity = "TRIP"

    label_name = coarse_name if mode == "coarse" else subsystem
    label_idx = FAULT_CLASS_TO_IDX[coarse_name] if mode == "coarse" else SUBSYSTEM_CLASS_TO_IDX[subsystem]

    return EventClassificationResult(
        label_idx=label_idx,
        label_name=label_name,
        subsystem=subsystem,
        subsystem_idx=SUBSYSTEM_CLASS_TO_IDX[subsystem],
        triage=triage,
        triage_idx=TRIAGE_CLASS_TO_IDX[triage],
        severity=severity,
        matched_events=[m["event"] for m in matched_by_priority],
        telemetry_flags=telemetry_flags,
    )



@dataclass
class NarrativeResult:
    """Rich Chain-of-Thought explanation and structured Language Model target.

    Supports 3-tuple unpacking (prompt, rationale, action = result) for full backward
    compatibility with existing code, while exposing .target (StructuredLMTarget).
    """

    prompt: str
    rationale: str
    action: str
    target: StructuredLMTarget

    def __iter__(self):
        yield self.prompt
        yield self.rationale
        yield self.action

    def __getitem__(self, index: int):
        if index == 0:
            return self.prompt
        elif index == 1:
            return self.rationale
        elif index == 2:
            return self.action
        raise IndexError("NarrativeResult index out of range (use .target for structured fields)")

    def __len__(self) -> int:
        return 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "rationale": self.rationale,
            "action": self.action,
            "structured_target": self.target.to_formatted_target(),
        }


def build_cot_narrative(
    label_name: str,
    signals_arr: np.ndarray,
    turbine_id: str,
    start_time: str,
    end_time: str,
    events: list[dict[str, Any]],
) -> NarrativeResult:
    """Generate physics-grounded Chain-of-Thought (CoT) explanation and structured Language Model target."""
    duration_hours = int(round(len(signals_arr) * 10 / 60)) if len(signals_arr) > 0 else 24
    prompt = (
        f"Analyze the {duration_hours}-hour turbine SCADA telemetry from {start_time} to {end_time} on {turbine_id}. "
        "Is there an abnormal condition developing? Provide your step-by-step reasoning and recommended maintenance action."
    )

    # Calculate window telemetry stats
    mean_wind = float(np.mean(signals_arr[:, 0]))
    mean_power = float(np.mean(signals_arr[:, 1]))
    max_power = float(np.max(signals_arr[:, 1]))
    mean_rotor = float(np.mean(signals_arr[:, 2]))
    mean_gen_rpm = float(np.mean(signals_arr[:, 3]))
    start_gear_temp = float(signals_arr[0, 4])
    end_gear_temp = float(signals_arr[-1, 4])
    gear_temp_delta = end_gear_temp - start_gear_temp
    max_gen_bearing = float(np.max(signals_arr[:, 5]))
    n_ch = signals_arr.shape[-1]
    # Pitch: mean of A/B/C when available; channel indices 6/7/8
    pitch_a = signals_arr[:, 6]
    pitch_b = signals_arr[:, 7] if n_ch > 7 else pitch_a
    pitch_c = signals_arr[:, 8] if n_ch > 8 else pitch_a
    mean_pitch = float(np.mean((pitch_a + pitch_b + pitch_c) / 3.0))
    pitch_spread = float(np.nanmax(np.max(np.stack([pitch_a, pitch_b, pitch_c], axis=0), axis=0) -
                                   np.min(np.stack([pitch_a, pitch_b, pitch_c], axis=0), axis=0)))
    vibe = signals_arr[:, 9] if n_ch > 9 else signals_arr[:, 7]
    max_vibe = float(np.max(vibe))
    ambient = signals_arr[:, 10] if n_ch > 10 else np.full_like(pitch_a, 12.0)
    mean_ambient = float(np.mean(ambient))

    # Determine canonical subsystem, coarse fault, and triage
    if label_name in SUBSYSTEM_CLASSES:
        subsystem = label_name
        coarse_fault = SUBSYSTEM_TO_COARSE_FAULT.get(subsystem, "Normal Operation")
    elif label_name in FAULT_CLASSES:
        coarse_fault = label_name
        subsystem = next(
            (k for k, v in SUBSYSTEM_TO_COARSE_FAULT.items() if v == coarse_fault and k != "normal_operation"),
            "normal_operation" if coarse_fault == "Normal Operation" else "manual_safety",
        )
    else:
        subsystem = "normal_operation"
        coarse_fault = "Normal Operation"

    if subsystem in ("environmental_stop", "curtailment_external"):
        triage = "benign_stop"
    elif subsystem == "normal_operation" or coarse_fault == "Normal Operation":
        triage = "normal"
    else:
        triage = "fault"


    # Extract event metadata if present
    ev_msg = ""
    ev_code = ""
    ev_iec = ""
    ev_svc = ""
    ev_comment = ""
    if events:
        first_ev = events[0]
        ev_msg = str(first_ev.get("message", "")).strip()
        ev_code = str(first_ev.get("code", "")).strip()
        ev_iec = str(first_ev.get("iec_category", "")).strip()
        ev_svc = str(first_ev.get("service_contract_category", "")).strip()
        for e in events:
            c = str(e.get("comment", "")).strip()
            if c:
                ev_comment = c
                break
    contract_note = f" (Contract: {ev_svc})" if ev_svc else ""
    comment_evidence = f" Field technician log note: '{ev_comment}'." if ev_comment else ""
    comment_cause = f" (Technician confirmed: '{ev_comment}')" if ev_comment else ""
    comment_action = f" Field work note: '{ev_comment}'." if ev_comment else ""

    # Calculate estimated impact (kWh)
    est_potential_power = min(2050.0, max(0.0, (mean_wind / 11.5) ** 3 * 2050.0)) if mean_wind >= 3.5 else 0.0
    est_lost_kwh = 0.0
    if events and (coarse_fault != "Normal Operation" or subsystem in ("curtailment_external", "environmental_stop")):
        dur_hrs = sum(float(e.get("duration", 600.0)) for e in events) / 3600.0
        dur_hrs = max(0.2, min(12.0, dur_hrs))
        est_lost_kwh = float(est_potential_power * dur_hrs)

    # Branch by subsystem / coarse fault for high fidelity physics narrative
    if coarse_fault == "Gearbox Overheating" or subsystem == "gearbox_lubrication":
        finding = f"Gearbox lubrication thermal warning on {turbine_id}."
        evidence = (
            f"Over the 12-hour observation window, the turbine operated with mean wind speed of {mean_wind:.1f} m/s "
            f"and generated average power of {mean_power:.1f} kW. However, the gearbox oil temperature exhibited an abnormal upward trend, "
            f"climbing from {start_gear_temp:.1f}°C to {end_gear_temp:.1f}°C (+{gear_temp_delta:.1f}°C rise) despite steady electrical load. "
            f"This divergence between generator output and gearbox thermal equilibrium indicates degraded heat dissipation in the lubrication loop."
        ) + comment_evidence
        cause_desc = f"{ev_msg} (SCADA Code {ev_code}){contract_note}" if ev_msg else "Degraded heat dissipation or oil filter restriction in gearbox lubrication loop"
        cause = f"Gearbox lubrication system anomaly: {cause_desc}.{comment_cause}"
        impact = f"Estimated {est_lost_kwh:.0f} kWh lost or at risk. Drivetrain thermal efficiency degraded."
        action = (
            "Diagnosis: Gearbox Thermal Overheating / Lubrication Fault. "
            "Action: Immediately curtail turbine active power to 50% rated capacity. "
            "Dispatch maintenance crew to inspect oil cooling radiator, check pump pressure, and sample oil for particulate degradation."
        ) + comment_action
    elif coarse_fault == "Generator Bearing Anomaly" or subsystem in ("generator_bearing", "generator_cooling"):
        subsys_label = "cooling circuit" if subsystem == "generator_cooling" else "bearing"
        finding = f"Generator {subsys_label} thermal anomaly on {turbine_id}."
        evidence = (
            f"Telemetry indicates sustained electrical generation averaging {mean_power:.1f} kW at generator speed {mean_gen_rpm:.0f} RPM. "
            f"Critically, drive-end generator bearing front temperature reached an elevated peak of {max_gen_bearing:.1f}°C under {mean_wind:.1f} m/s wind. "
            f"The bearing thermal trajectory reflects abnormal friction, preceding potential bearing raceway spalling."
        ) + comment_evidence
        cause_desc = f"{ev_msg} (SCADA Code {ev_code})" if ev_msg else f"Thermal overload in generator {subsys_label}"
        cause = f"Generator {subsys_label} fault: {cause_desc}.{comment_cause}"
        impact = f"Estimated {est_lost_kwh:.0f} kWh lost. Elevated thermal wear on generator components."
        action = (
            "Diagnosis: Generator Bearing Thermal Anomaly. "
            "Action: Schedule off-peak acoustic/vibration greasing diagnostic. "
            "Curtail max generator RPM if bearing temperature exceeds 85°C."
        ) + comment_action
    elif coarse_fault == "Pitch / Aerodynamic Fault" or subsystem in ("pitch_system", "structural_overspeed"):
        finding = f"Blade pitch actuator imbalance and drivetrain vibration anomaly on {turbine_id}."
        evidence = (
            f"Wind speed averaged {mean_wind:.1f} m/s, but blade pitch angle showed rapid oscillations (mean: {mean_pitch:.1f}°) "
            f"correlated with drivetrain acceleration shocks peaking at {max_vibe:.1f} mm/s². "
            f"This asymmetric aerodynamic loading creates significant cyclic stress across the low-speed shaft."
        ) + comment_evidence
        cause_desc = f"{ev_msg} (SCADA Code {ev_code})" if ev_msg else "Pitch actuator cylinder pressure leakage or encoder deviation"
        cause = f"Aerodynamic / pitch system fault: {cause_desc}.{comment_cause}"
        impact = f"Estimated {est_lost_kwh:.0f} kWh lost. Cyclic fatigue risk on blade root bolts and main bearing."
        action = (
            "Diagnosis: Pitch Actuator / Aerodynamic Imbalance. "
            "Action: Initiate automated pitch angle calibration sequence. "
            "Inspect hydraulic pitch actuators and cylinder seals for pressure leakage."
        ) + comment_action
    elif coarse_fault == "Turbine Trip / Forced Outage" or subsystem in (
        "brake_hydraulics", "converter_grid", "yaw_cable", "sensor_comms", "manual_safety"
    ):
        finding = f"Turbine safety trip and forced outage ({subsystem}) on {turbine_id}."
        evidence = (
            f"The turbine experienced an abrupt generation drop from {max_power:.1f} kW to 0.0 kW within a single 10-minute timestep. "
            f"Rotor speed braked from {mean_rotor:.1f} RPM down to idle (~0 RPM), while blade pitch feathered immediately to 90°."
        ) + comment_evidence
        cause_desc = f"{ev_msg} (SCADA Code {ev_code}, IEC: {ev_iec or 'Forced outage'})" if ev_msg else f"Safety loop trip in {subsystem}"
        cause = f"Turbine trip: {cause_desc}.{comment_cause}"
        impact = f"Estimated {est_lost_kwh:.0f} kWh lost during stoppage. Machine in non-operational state."
        action = (
            "Diagnosis: Turbine Safety Trip / Emergency Forced Outage. "
            "Action: Review SCADA safety loop circuit logs, verify grid connection breaker status, and verify clearance before remote reset."
        ) + comment_action
    elif subsystem in ("environmental_stop", "curtailment_external"):
        is_curtail = subsystem == "curtailment_external"
        state_label = "external curtailment" if is_curtail else "low-wind environmental standby"
        finding = f"Turbine in {state_label} on {turbine_id}."
        evidence = (
            f"Over the 12-hour period, wind speed was {mean_wind:.1f} m/s and power averaged {mean_power:.1f} kW. "
            f"The turbine was in an operational standby or curtailment state due to ambient conditions or dispatch setpoints."
        ) + comment_evidence
        cause_desc = f"{ev_msg} (Code {ev_code})" if ev_msg else f"Operational {state_label}"
        cause = f"{state_label.capitalize()}: {cause_desc}.{comment_cause}"
        impact = f"{est_lost_kwh:.0f} kWh curtailed. Automatic resumption upon environmental or dispatch release."
        action = (
            "Diagnosis: Environmental Standby / External Curtailment. "
            "Action: No maintenance intervention required. Automatic resumption upon environmental or dispatch release."
        ) + comment_action
    else:  # Normal Operation / normal_operation
        finding = f"Nominal operation within normal design envelope on {turbine_id}."
        evidence = (
            f"Wind turbine operated within normal design envelope over the 12-hour period. Average wind speed was {mean_wind:.1f} m/s "
            f"with consistent power generation averaging {mean_power:.1f} kW. Gearbox oil temperature ({end_gear_temp:.1f}°C) "
            f"and generator bearing temperature ({max_gen_bearing:.1f}°C) remained well within safe thermal thresholds. Drivetrain vibration was low ({max_vibe:.1f} mm/s²)."
        ) + comment_evidence
        cause = f"Nominal operation: All turbine subsystems and SCADA signals operating within design specifications.{comment_cause}"
        impact = f"0 kWh lost. Total active generation: {mean_power * (len(signals_arr) * 10.0 / 60.0):.0f} kWh over the 12-hour window."
        action = (
            "Diagnosis: Normal Operation. "
            "Action: No maintenance intervention required. Continue continuous telemetry monitoring."
        ) + comment_action

    rationale = f"{evidence} {cause}"
    target = StructuredLMTarget(
        finding=finding,
        evidence=evidence,
        cause=cause,
        impact=impact,
        action=action,
        subsystem=subsystem,
        triage=triage,
        coarse_fault=coarse_fault,
        comment=ev_comment,
        code=ev_code,
        iec_category=ev_iec,
        service_contract_category=ev_svc,
    )
    return NarrativeResult(prompt=prompt, rationale=rationale, action=action, target=target)




def generate_synthetic_scada_windows(
    num_turbines: int | None = None,
    windows_per_turbine: int = 50,
    seed: int = 42,
    farm: str = "penmanshiel",
    turbines: list[str] | None = None,
) -> list[TelemetryWindow]:
    """Generates realistic, physically consistent synthetic SCADA windows for Penmanshiel or Kelmarsh."""
    np.random.seed(seed)
    windows = []
    base_time = datetime.datetime(2020, 1, 1, 0, 0, tzinfo=datetime.UTC)

    if turbines is not None:
        turb_list = list(turbines)
    elif farm.lower() == "penmanshiel":
        turb_list = PENMANSHIEL_TURBINES if num_turbines is None else PENMANSHIEL_TURBINES[:num_turbines]
    else:
        turb_list = KELMARSH_TURBINES if num_turbines is None else KELMARSH_TURBINES[:num_turbines]

    for turb_idx, turbine_id in enumerate(turb_list, start=1):
        curr_time = base_time + datetime.timedelta(days=turb_idx * 15)

        for w_idx in range(windows_per_turbine):
            start_t = curr_time
            end_t = start_t + datetime.timedelta(minutes=10 * WINDOW_STEPS)
            curr_time = end_t + datetime.timedelta(hours=2)

            # Determine condition type: 65% normal, 35% anomalies
            rand_val = np.random.rand()
            if rand_val < 0.65:
                label_idx = 0
            elif rand_val < 0.75:
                label_idx = 1  # Gearbox Overheating
            elif rand_val < 0.85:
                label_idx = 2  # Generator Bearing Anomaly
            elif rand_val < 0.93:
                label_idx = 3  # Pitch / Aerodynamic Fault
            else:
                label_idx = 4  # Trip / Outage

            label_name = IDX_TO_FAULT_CLASS[label_idx]

            # Synthesize realistic time series
            duration_hrs = WINDOW_STEPS * 10.0 / 60.0
            t = np.linspace(0, duration_hrs, WINDOW_STEPS)

            # Ambient temperature: seasonal sine + diurnal variation + noise
            day_of_year = ((start_t - base_time).days % 365)
            seasonal_offset = 10.0 * np.sin(2 * np.pi * day_of_year / 365)  # +/-10°C seasonal
            diurnal = 3.0 * np.sin(2 * np.pi * t / 24.0)
            ambient_temp = 12.0 + seasonal_offset + diurnal + np.random.normal(0, 0.5, WINDOW_STEPS)

            wind_speed = np.clip(np.random.normal(8.0, 2.0) + np.sin(t / 2) * 1.5 + np.random.normal(0, 0.3, WINDOW_STEPS), 2.0, 22.0)

            # Power curve: P ≈ 0.5 * rho * A * Cp * v^3 capped at 2050 kW (Senvion MM82/MM92)
            power = np.clip(np.where(wind_speed < 3.0, 0.0, np.minimum(2050.0, (wind_speed / 11.5) ** 3 * 2050.0)), 0, 2050)
            power += np.random.normal(0, 25.0, WINDOW_STEPS)

            rotor_speed = np.where(power > 50, 10.0 + (power / 2050.0) * 5.0 + np.random.normal(0, 0.2, WINDOW_STEPS), 2.0)
            gen_rpm = rotor_speed * 105.0 + np.random.normal(0, 5.0, WINDOW_STEPS)

            # Thermal models with time lag, referenced to ambient for thermal aliasing removal
            base_excess = 43.0 + (power / 2050.0) * 15.0  # gear_oil excess above ambient
            gear_oil_temp = ambient_temp + base_excess + np.random.normal(0, 0.5, WINDOW_STEPS)
            gen_bearing_temp = ambient_temp + 38.0 + (power / 2050.0) * 20.0 + np.random.normal(0, 0.5, WINDOW_STEPS)

            # Aerodynamic pitch control curve: all 3 blades nominally identical + small independent noise
            pitch_base = np.where(wind_speed > 12.0, (wind_speed - 12.0) * 3.5, 0.5)
            pitch_angle_a = pitch_base + np.random.normal(0, 0.15, WINDOW_STEPS)
            pitch_angle_b = pitch_base + np.random.normal(0, 0.15, WINDOW_STEPS)
            pitch_angle_c = pitch_base + np.random.normal(0, 0.15, WINDOW_STEPS)

            drivetrain_accel = 15.0 + (rotor_speed / 15.0) * 25.0 + np.random.normal(0, 2.0, WINDOW_STEPS)

            events = []
            if label_idx == 1:  # Gearbox Overheating — progressive lubrication degradation
                gear_oil_temp += np.linspace(0, 35.0, WINDOW_STEPS)  # ramp to ~+35°C excess
                # Add subtle oscillation to mimic oil circulation pump cycling
                gear_oil_temp += 2.0 * np.sin(t * 0.8) * np.linspace(0.5, 1.0, WINDOW_STEPS)
                events.append({"start": end_t - datetime.timedelta(hours=2), "message": "High gearbox oil temperature warning", "status": "Warning", "code": "1910"})
            elif label_idx == 2:  # Generator Bearing Anomaly — thermal runaway
                gen_bearing_temp += np.linspace(0, 38.0, WINDOW_STEPS)
                # Slight vibration increase as bearing degrades
                drivetrain_accel += np.linspace(0, 15.0, WINDOW_STEPS) + np.random.exponential(5.0, WINDOW_STEPS)
                events.append({"start": end_t - datetime.timedelta(hours=1), "message": "Generator bearing temperature trip warning", "status": "Warning", "code": "2910"})
            elif label_idx == 3:  # Pitch System Fault — blade asymmetry (one blade runs away)
                # Pick one faulty blade; others stay normal — creates clear inter-blade spread
                faulty_blade = np.random.choice([0, 1, 2])
                asymmetry_start = int(WINDOW_STEPS * 0.3)  # fault develops partway through window
                runaway_profile = np.zeros(WINDOW_STEPS)
                runaway_profile[asymmetry_start:] = np.linspace(0, np.random.uniform(8.0, 18.0), WINDOW_STEPS - asymmetry_start)
                runaway_profile += np.random.normal(0, 0.3, WINDOW_STEPS)
                if faulty_blade == 0:
                    pitch_angle_a += runaway_profile
                elif faulty_blade == 1:
                    pitch_angle_b += runaway_profile
                else:
                    pitch_angle_c += runaway_profile
                # Resulting power dip and vibration from rotor imbalance
                power[asymmetry_start:] *= np.linspace(1.0, 0.85, WINDOW_STEPS - asymmetry_start)
                drivetrain_accel[asymmetry_start:] += np.random.exponential(30.0, WINDOW_STEPS - asymmetry_start)
                events.append({"start": end_t - datetime.timedelta(minutes=30), "message": "Pitch symmetry error / high vibration", "status": "Warning", "code": "3100"})
            elif label_idx == 4:  # Trip / Outage
                cut = int(WINDOW_STEPS * 0.7)
                power[cut:] = 0.0
                rotor_speed[cut:] = 0.5
                gen_rpm[cut:] = 0.0
                pitch_angle_a[cut:] = 89.0
                pitch_angle_b[cut:] = 89.0
                pitch_angle_c[cut:] = 89.0
                events.append({"start": start_t + datetime.timedelta(minutes=cut * 10), "message": "Emergency stop nacelle", "status": "Stop", "code": "20", "iec_category": "Forced outage"})

            # Pack 11 channels: shape (WINDOW_STEPS, 11)
            # Order: wind(0), power(1), rotor(2), gen_rpm(3), gear_oil(4), gen_bearing(5),
            #        pitch_a(6), pitch_b(7), pitch_c(8), drivetrain_accel(9), ambient_temp(10)
            signals_mat = np.stack(
                [
                    wind_speed,
                    power,
                    rotor_speed,
                    gen_rpm,
                    gear_oil_temp,
                    gen_bearing_temp,
                    pitch_angle_a,
                    pitch_angle_b,
                    pitch_angle_c,
                    drivetrain_accel,
                    ambient_temp,
                ],
                axis=-1,
            ).astype(np.float32)

            narrative = build_cot_narrative(
                label_name=label_name,
                signals_arr=signals_mat,
                turbine_id=turbine_id,
                start_time=start_t.strftime("%Y-%m-%d %H:%M"),
                end_time=end_t.strftime("%Y-%m-%d %H:%M"),
                events=events,
            )

            windows.append(
                TelemetryWindow(
                    turbine_id=turbine_id,
                    start_time=start_t.isoformat(),
                    end_time=end_t.isoformat(),
                    signals=signals_mat,
                    channel_names=SIGNAL_NAMES,
                    label_idx=label_idx,
                    label_name=label_name,
                    prompt=narrative.prompt,
                    rationale=narrative.rationale,
                    action=narrative.action,
                    status_events=events,
                    structured_target=narrative.target,
                )
            )

    return windows


def slice_real_scada_windows(
    telemetry_df: pd.DataFrame,
    status_events: list[dict[str, Any]],
    turbine_id: str,
    window_steps: int = WINDOW_STEPS,
    mode: str = "coarse",
    min_event_interval_steps: int = 6,
    include_normal: bool = True,
    normal_ratio: float = 1.0,
    seed: int = 42,
) -> list[TelemetryWindow]:
    """Slice real continuous SCADA telemetry and align status events to generate TelemetryWindows with LM targets.

    Parameters:
        telemetry_df: DataFrame of 8 canonical channels indexed by UTC DatetimeIndex.
        status_events: Parsed status log event dicts.
        turbine_id: Turbine identifier.
        window_steps: Timesteps per window (default: 72 = 12h).
        mode: Label space ('coarse' or 'subsystem').
        min_event_interval_steps: Minimum spacing between consecutive sliced event windows.
        include_normal: Whether to sample normal operation windows.
        normal_ratio: Number of normal windows per positive event window.
        seed: Random seed for sampling.

    Returns:
        List of TelemetryWindow instances.
    """
    rng = np.random.RandomState(seed)
    windows: list[TelemetryWindow] = []

    # Ensure chronological order
    telemetry_df = telemetry_df.sort_index()
    times = telemetry_df.index
    total_steps = len(telemetry_df)
    if total_steps < window_steps:
        return windows

    signals_raw = telemetry_df[SIGNAL_NAMES].to_numpy(dtype=np.float32)

    # 1. Filter for relevant events
    relevant_events = []
    for ev in status_events:
        st = str(ev.get("status", "")).lower()
        iec = str(ev.get("iec_category", "")).lower()
        msg = str(ev.get("message", "")).lower()
        code = str(ev.get("code", "")).strip()
        svc = str(ev.get("service_contract_category", "")).strip()
        comm = str(ev.get("comment", "")).strip()
        is_relevant = (
            "stop" in st
            or "warn" in st
            or "curtail" in st
            or "comm" in st
            or "trip" in st
            or "outage" in iec
            or "maintenance" in iec
            or "wind < start wind" in msg
            or code in HIGH_FREQUENCY_CODE_MAP
            or svc in SERVICE_CONTRACT_CATEGORY_MAP
            or bool(comm)
        )
        if is_relevant:
            relevant_events.append(ev)


    relevant_events.sort(key=lambda x: x["start"])

    # 2. Slice positive event windows
    last_end_idx = -window_steps
    for ev in relevant_events:
        ev_start = ev["start"]
        idx_pos = times.searchsorted(ev_start)
        if idx_pos < window_steps or idx_pos >= total_steps:
            continue

        # Prevent overlapping identical slices
        if idx_pos - last_end_idx < min_event_interval_steps:
            continue

        start_idx = idx_pos - window_steps
        end_idx = idx_pos
        last_end_idx = idx_pos

        w_signals = signals_raw[start_idx:end_idx]
        w_start_time = times[start_idx]
        w_end_time = times[end_idx - 1]

        # Gather all events within this slice window
        events_in_slice = [
            e for e in status_events
            if e["start"] >= w_start_time and e["start"] <= w_end_time
        ]
        if not events_in_slice:
            events_in_slice = [ev]

        class_res = classify_window_events(events_in_slice, signals_arr=w_signals, mode=mode)
        narrative = build_cot_narrative(
            label_name=class_res.label_name,
            signals_arr=w_signals,
            turbine_id=turbine_id,
            start_time=w_start_time.strftime("%Y-%m-%d %H:%M"),
            end_time=w_end_time.strftime("%Y-%m-%d %H:%M"),
            events=events_in_slice,
        )

        windows.append(
            TelemetryWindow(
                turbine_id=turbine_id,
                start_time=w_start_time.isoformat(),
                end_time=w_end_time.isoformat(),
                signals=w_signals,
                channel_names=SIGNAL_NAMES,
                label_idx=class_res.label_idx,
                label_name=class_res.label_name,
                prompt=narrative.prompt,
                rationale=narrative.rationale,
                action=narrative.action,
                status_events=events_in_slice,
                structured_target=narrative.target,
            )
        )

    # 3. Sample negative / normal operational windows
    if include_normal and len(windows) > 0:
        target_normal_count = int(len(windows) * normal_ratio)
        event_times = [e["start"] for e in relevant_events]
        stride = max(window_steps, 36)
        candidate_indices = list(range(0, total_steps - window_steps, stride))
        rng.shuffle(candidate_indices)

        normal_added = 0
        for s_idx in candidate_indices:
            if normal_added >= target_normal_count:
                break
            w_start = times[s_idx]
            w_end = times[s_idx + window_steps - 1]

            # Check if any fault event happened in window or in the subsequent 6h
            buffer_end = w_end + pd.Timedelta(hours=6)
            has_event = any(w_start <= et <= buffer_end for et in event_times)
            if has_event:
                continue

            w_signals = signals_raw[s_idx : s_idx + window_steps]
            mean_p = float(np.mean(w_signals[:, 1]))
            mean_w = float(np.mean(w_signals[:, 0]))
            if mean_p < 20.0 and mean_w > 4.5:
                continue

            class_res = classify_window_events([], signals_arr=w_signals, mode=mode)
            narrative = build_cot_narrative(
                label_name=class_res.label_name,
                signals_arr=w_signals,
                turbine_id=turbine_id,
                start_time=w_start.strftime("%Y-%m-%d %H:%M"),
                end_time=w_end.strftime("%Y-%m-%d %H:%M"),
                events=[],
            )

            windows.append(
                TelemetryWindow(
                    turbine_id=turbine_id,
                    start_time=w_start.isoformat(),
                    end_time=w_end.isoformat(),
                    signals=w_signals,
                    channel_names=SIGNAL_NAMES,
                    label_idx=class_res.label_idx,
                    label_name=class_res.label_name,
                    prompt=narrative.prompt,
                    rationale=narrative.rationale,
                    action=narrative.action,
                    status_events=[],
                    structured_target=narrative.target,
                )
            )
            normal_added += 1

    return windows


def process_real_turbine_data(
    telemetry_path: str | Path,
    status_path: str | Path,
    turbine_id: str,
    window_steps: int = WINDOW_STEPS,
    mode: str = "coarse",
    include_normal: bool = True,
    normal_ratio: float = 1.0,
    seed: int = 42,
) -> list[TelemetryWindow]:
    """Parse real Greenbyte SCADA telemetry and status CSV files into TelemetryWindows with LM targets."""
    scada_df = parse_greenbyte_csv(Path(telemetry_path))
    feats, _ = extract_scada_features(scada_df)
    status_df = parse_greenbyte_csv(Path(status_path))
    events = parse_status_events(status_df)
    return slice_real_scada_windows(
        telemetry_df=feats,
        status_events=events,
        turbine_id=turbine_id,
        window_steps=window_steps,
        mode=mode,
        include_normal=include_normal,
        normal_ratio=normal_ratio,
        seed=seed,
    )

