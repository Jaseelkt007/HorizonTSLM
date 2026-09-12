"""Tests for SCADA event classification, subsystem taxonomy mapping, and telemetry verification."""

import numpy as np
import pytest

from mk.src.data.preprocessor import (
    build_cot_narrative,
    check_telemetry_anomalies,
    classify_window_events,
)
from mk.src.data.schemas import (
    FAULT_CLASS_TO_IDX,
    SUBSYSTEM_CLASS_TO_IDX,
    SUBSYSTEM_CLASSES,
    TRIAGE_CLASS_TO_IDX,
    WINDOW_STEPS,
)


def _make_dummy_signals(
    wind: float = 8.0,
    power: float = 1200.0,
    gear_oil: float = 58.0,
    gen_bearing: float = 55.0,
    pitch: float = 1.0,
    vibe: float = 25.0,
) -> np.ndarray:
    """Create a nominal (72, 8) signals array."""
    arr = np.zeros((WINDOW_STEPS, 8), dtype=np.float32)
    arr[:, 0] = wind
    arr[:, 1] = power
    arr[:, 2] = 12.0
    arr[:, 3] = 1250.0
    arr[:, 4] = gear_oil
    arr[:, 5] = gen_bearing
    arr[:, 6] = pitch
    arr[:, 7] = vibe
    return arr


def test_classify_normal_operation_unpacking():
    """Verify that empty event window yields Normal Operation and unpacks like a 2-tuple."""
    signals = _make_dummy_signals()
    res = classify_window_events(events_in_window=[], signals_arr=signals)

    # Tuple unpacking check
    label_idx, label_name = res
    assert label_idx == FAULT_CLASS_TO_IDX["Normal Operation"]
    assert label_name == "Normal Operation"
    assert len(res) == 2
    assert res[0] == label_idx
    assert res[1] == label_name

    # Rich metadata check
    assert res.subsystem == "normal_operation"
    assert res.subsystem_idx == SUBSYSTEM_CLASS_TO_IDX["normal_operation"]
    assert res.triage == "normal"
    assert res.triage_idx == TRIAGE_CLASS_TO_IDX["normal"]
    assert res.severity == "NOMINAL"
    assert isinstance(res.to_dict(), dict)


@pytest.mark.parametrize(
    "message,status,expected_subsystem,expected_coarse,expected_triage,expected_severity",
    [
        (
            "Overload generator fan 2",
            "Warning",
            "generator_cooling",
            "Generator Bearing Anomaly",
            "fault",
            "WARNING",
        ),
        (
            "Generator bearing front temperature high",
            "Warning",
            "generator_bearing",
            "Generator Bearing Anomaly",
            "fault",
            "WARNING",
        ),
        (
            "Brake accumulator defect",
            "Stop",
            "brake_hydraulics",
            "Turbine Trip / Forced Outage",
            "fault",
            "TRIP",
        ),
        (
            "Pitch measuring system 1><2",
            "Warning",
            "pitch_system",
            "Pitch / Aerodynamic Fault",
            "fault",
            "WARNING",
        ),
        (
            "Frequency converter error BP52",
            "Stop",
            "converter_grid",
            "Turbine Trip / Forced Outage",
            "fault",
            "TRIP",
        ),
        (
            "Low gearbox oil pressure",
            "Warning",
            "gearbox_lubrication",
            "Gearbox Overheating",
            "fault",
            "WARNING",
        ),
        (
            "Tower oscillation X level 2",
            "Warning",
            "structural_overspeed",
            "Pitch / Aerodynamic Fault",
            "fault",
            "WARNING",
        ),
        (
            "Cable autounwind operation active",
            "Warning",
            "yaw_cable",
            "Turbine Trip / Forced Outage",
            "fault",
            "WARNING",
        ),
        (
            "Comm. failure FPM module",
            "Warning",
            "sensor_comms",
            "Turbine Trip / Forced Outage",
            "fault",
            "WARNING",
        ),
        (
            "Wind < start wind",
            "Stop",
            "environmental_stop",
            "Normal Operation",
            "benign_stop",
            "TRIP",
        ),
        (
            "P output externally reduced by DSO",
            "Warning",
            "curtailment_external",
            "Normal Operation",
            "benign_stop",
            "WARNING",
        ),
        (
            "Emergency stop button pressed",
            "Stop",
            "manual_safety",
            "Turbine Trip / Forced Outage",
            "fault",
            "TRIP",
        ),
    ],
)
def test_classify_subsystem_mappings(
    message,
    status,
    expected_subsystem,
    expected_coarse,
    expected_triage,
    expected_severity,
):
    """Verify each canonical subsystem pattern maps correctly to subsystem, coarse class, and triage."""
    events = [{"message": message, "status": status, "code": "100"}]
    signals = _make_dummy_signals()

    # Default coarse mode
    res = classify_window_events(events, signals_arr=signals, mode="coarse")
    assert res.label_name == expected_coarse
    assert res.subsystem == expected_subsystem
    assert res.triage == expected_triage
    assert res.severity == expected_severity

    # Subsystem mode
    res_sub = classify_window_events(events, signals_arr=signals, mode="subsystem")
    assert res_sub.label_name == expected_subsystem
    assert res_sub.label_idx == SUBSYSTEM_CLASS_TO_IDX[expected_subsystem]


def test_telemetry_anomaly_detection_gearbox():
    """Verify telemetry with thermal surge is detected even without event logs."""
    signals = _make_dummy_signals(gear_oil=45.0)
    signals[:, 4] = np.linspace(45.0, 72.0, WINDOW_STEPS)  # Delta +27C and max > 65C

    flags = check_telemetry_anomalies(signals)
    assert flags["high_gear_oil_temp"] is True

    res = classify_window_events(events_in_window=[], signals_arr=signals)
    assert res.subsystem == "gearbox_lubrication"
    assert res.label_name == "Gearbox Overheating"
    assert res.triage == "fault"


def test_telemetry_power_trip_detection():
    """Verify sudden generation drop while wind is above cut-in is flagged as trip."""
    signals = _make_dummy_signals(wind=9.0, power=1400.0, pitch=1.0)
    # Collapse power in last quarter
    cut = int(WINDOW_STEPS * 0.75)
    signals[cut:, 1] = 0.0
    signals[cut:, 6] = 88.0  # blades feathered to 88 deg

    flags = check_telemetry_anomalies(signals)
    assert flags["power_trip"] is True

    res = classify_window_events(events_in_window=[], signals_arr=signals)
    assert res.severity == "TRIP"
    assert res.label_name == "Turbine Trip / Forced Outage"


def test_priority_resolution_multi_event():
    """Verify that a critical component fault takes priority over minor informational logs."""
    events = [
        {"message": "Wind < start wind", "status": "Stop"},  # benign
        {"message": "Overload gear oil pump", "status": "Stop"},  # critical fault
        {"message": "Routine comms handshake", "status": "Informational"},  # info
    ]
    res = classify_window_events(events, signals_arr=_make_dummy_signals())
    assert res.subsystem == "gearbox_lubrication"
    assert res.triage == "fault"
    assert res.severity == "TRIP"


def test_build_cot_narrative_subsystems():
    """Ensure build_cot_narrative produces coherent rationale for new subsystem names."""
    signals = _make_dummy_signals()
    for sub in SUBSYSTEM_CLASSES:
        prompt, rationale, action = build_cot_narrative(
            label_name=sub,
            signals_arr=signals,
            turbine_id="Penmanshiel WT01",
            start_time="2020-01-01 00:00",
            end_time="2020-01-01 12:00",
            events=[],
        )
        assert len(prompt) > 20
        assert len(rationale) > 20
        assert len(action) > 20
        assert "Diagnosis:" in action


def test_structured_lm_target_formatting():
    """Verify that StructuredLMTarget produces standardized 5-line report with Answer token."""
    signals = _make_dummy_signals(gear_oil=50.0)
    signals[:, 4] = np.linspace(50.0, 75.0, WINDOW_STEPS)
    events = [
        {
            "message": "Low gearbox oil pressure",
            "status": "Warning",
            "code": "1910",
            "service_contract_category": "Mechanical error (23)",
            "iec_category": "Forced outage",
            "duration": 1800.0,
        }
    ]
    res = build_cot_narrative(
        label_name="gearbox_lubrication",
        signals_arr=signals,
        turbine_id="Penmanshiel WT11",
        start_time="2020-01-01 00:00",
        end_time="2020-01-01 12:00",
        events=events,
    )

    # Check 3-tuple unpacking
    p, r, a = res
    assert len(p) > 0 and len(r) > 0 and len(a) > 0

    # Check target attribute
    target = res.target
    assert target is not None
    assert target.subsystem == "gearbox_lubrication"
    assert "Penmanshiel WT11" in target.finding
    assert "gearbox oil temperature" in target.evidence.lower()
    assert "SCADA Code 1910" in target.cause
    assert "Action:" in target.action

    # Check standardized target output format
    formatted = target.to_formatted_target()
    assert formatted.startswith("FINDING   ")
    assert "EVIDENCE  " in formatted
    assert "CAUSE     " in formatted
    assert "IMPACT    " in formatted
    assert "ACTION    " in formatted
    assert formatted.endswith("Answer: gearbox_lubrication")


def test_parse_status_events_with_categories():
    """Verify parse_status_events extracts Code, Service Contract Category, and IEC Category."""
    import pandas as pd

    from mk.src.data.preprocessor import parse_status_events

    df = pd.DataFrame(
        {
            "Timestamp start": ["2017-01-01 08:00:00", "2017-01-01 12:00:00"],
            "Timestamp end": ["2017-01-01 09:30:00", "2017-01-01 13:00:00"],
            "Duration": [5400, 3600],
            "Status": ["Stop", "Warning"],
            "Code": ["41", "2125"],
            "Message": ["Islanding detection", "Timeout brake closed"],
            "Service contract category": ["External stop (grid) (4)", "Warnings (27)"],
            "IEC category": ["Technical Standby", "Full Performance"],
            "Comment": ["HV trip", ""],
        }
    )

    events = parse_status_events(df)
    assert len(events) == 2
    ev1 = events[0]
    assert ev1["code"] == "41"
    assert ev1["message"] == "Islanding detection"
    assert ev1["service_contract_category"] == "External stop (grid) (4)"
    assert ev1["iec_category"] == "Technical Standby"
    assert ev1["comment"] == "HV trip"
    assert ev1["duration"] == 5400.0


def test_slice_real_scada_windows_mock():
    """Verify slice_real_scada_windows creates TelemetryWindows with structured targets."""
    import pandas as pd

    from mk.src.data.preprocessor import SIGNAL_NAMES, slice_real_scada_windows

    # Create 144 steps of continuous telemetry (24h)
    times = pd.date_range("2020-01-01 00:00:00", periods=144, freq="10min", tz="UTC")
    data = np.zeros((144, len(SIGNAL_NAMES)), dtype=np.float32)
    data[:, 0] = 8.5   # wind speed
    data[:, 1] = 1200.0 # power
    telemetry_df = pd.DataFrame(data, index=times, columns=SIGNAL_NAMES)

    # One stop event at step 100
    event_time = times[100]
    events = [
        {
            "start": event_time,
            "end": event_time + pd.Timedelta(minutes=30),
            "duration": 1800.0,
            "status": "Stop",
            "code": "20",
            "message": "Emergency stop nacelle",
            "service_contract_category": "Safety stop of WEC (15)",
            "iec_category": "Forced outage",
            "comment": "",
        }
    ]

    windows = slice_real_scada_windows(
        telemetry_df=telemetry_df,
        status_events=events,
        turbine_id="Penmanshiel WT05",
        window_steps=72,
        include_normal=True,
        normal_ratio=1.0,
    )

    assert len(windows) >= 1
    w = windows[0]
    assert w.turbine_id == "Penmanshiel WT05"
    assert w.signals.shape == (72, 8)
    assert w.structured_target is not None
    assert "Penmanshiel WT05" in w.structured_target.finding
    assert "Emergency stop nacelle" in w.structured_target.cause


def test_technician_comment_injection():
    """Verify that human technician comments from field logs are injected into LM targets."""
    signals = _make_dummy_signals(gear_oil=65.0)
    events = [
        {
            "start": "2020-01-01 10:00:00",
            "end": "2020-01-01 12:00:00",
            "duration": 7200.0,
            "status": "Stop",
            "code": "1550",
            "message": "Missing gear oil (high rpm)",
            "service_contract_category": "Mechanical error (23)",
            "iec_category": "Forced outage",
            "comment": "Gear oil hose damage - Top up oil 40L",
        }
    ]

    res = build_cot_narrative(
        label_name="gearbox_lubrication",
        signals_arr=signals,
        turbine_id="Penmanshiel WT04",
        start_time="2020-01-01 00:00",
        end_time="2020-01-01 12:00",
        events=events,
    )

    target = res.target
    assert target.comment == "Gear oil hose damage - Top up oil 40L"
    assert "Gear oil hose damage - Top up oil 40L" in target.evidence
    assert "Technician confirmed: 'Gear oil hose damage - Top up oil 40L'" in target.cause
    assert "Field work note: 'Gear oil hose damage - Top up oil 40L'" in target.action


@pytest.mark.parametrize(
    "code,status,expected_subsystem,expected_coarse",
    [
        ("1550", "Stop", "gearbox_lubrication", "Gearbox Overheating"),
        ("111", "Curtailment", "curtailment_external", "Normal Operation"),
        ("108", "Curtailment", "curtailment_external", "Normal Operation"),
        ("9997", "Communication", "sensor_comms", "Turbine Trip / Forced Outage"),
        ("3125", "Stop", "converter_grid", "Turbine Trip / Forced Outage"),
        ("4510", "Stop", "structural_overspeed", "Pitch / Aerodynamic Fault"),
        ("64", "Stop", "environmental_stop", "Normal Operation"),
        ("710", "Stop", "manual_safety", "Turbine Trip / Forced Outage"),
        ("6200", "Stop", "yaw_cable", "Turbine Trip / Forced Outage"),
    ],
)
def test_high_frequency_code_deterministic_classification(
    code, status, expected_subsystem, expected_coarse
):
    """Verify deterministic mapping of high-frequency SCADA codes from data_structure_report.md."""
    events = [{"message": "Vendor internal log", "status": status, "code": code}]
    signals = _make_dummy_signals()

    res = classify_window_events(events, signals_arr=signals, mode="subsystem")
    assert res.subsystem == expected_subsystem
    assert res.label_name == expected_subsystem

    res_coarse = classify_window_events(events, signals_arr=signals, mode="coarse")
    assert res_coarse.label_name == expected_coarse


def test_service_contract_category_fallback():
    """Verify classification falls back to Service Contract Category when code is unmapped."""
    events = [
        {
            "message": "Custom vendor event without pattern",
            "status": "Stop",
            "code": "99999",
            "service_contract_category": "Pitch errors (18)",
            "iec_category": "Forced outage",
        }
    ]
    signals = _make_dummy_signals()
    res = classify_window_events(events, signals_arr=signals, mode="subsystem")
    assert res.subsystem == "pitch_system"
    assert res.label_name == "pitch_system"


def test_extended_11_col_status_parsing():
    """Verify parsing of extended 11-column status files (2021+ schema) with string duration."""
    import pandas as pd

    from mk.src.data.preprocessor import parse_status_events

    df = pd.DataFrame(
        {
            "Timestamp start": ["2021-06-01 08:00:00"],
            "Timestamp end": ["2021-06-01 09:30:00"],
            "Duration": ["01:30:00"],
            "Status": ["Stop"],
            "Code": ["3210"],
            "Message": ["Frequency converter load rejection"],
            "Comment": ["Tower Bus Bar Blown"],
            "Service contract category": ["Generator and Converter errors (20)"],
            "IEC category": ["Forced outage"],
            "Global contract category": ["Global Outage"],
            "Custom contract category": ["Site Specific ANM"],
        }
    )

    events = parse_status_events(df)
    assert len(events) == 1
    ev = events[0]
    assert ev["code"] == "3210"
    assert ev["comment"] == "Tower Bus Bar Blown"
    assert ev["duration"] == 5400.0  # 1h 30m in seconds
    assert ev["global_contract_category"] == "Global Outage"
    assert ev["custom_contract_category"] == "Site Specific ANM"


def test_parse_greenbyte_csv_header_detection(tmp_path):
    """Verify parse_greenbyte_csv correctly finds '# Date and time' header and strips '#' from columns."""
    from mk.src.data.preprocessor import parse_greenbyte_csv

    csv_file = tmp_path / "test_scada.csv"
    csv_file.write_text(
        "# Greenbyte Export 2022\n"
        "# Turbine: Penmanshiel 01\n"
        "# Time interval: 2016-01-01 00:00:00 - 2017-01-01 00:00:00\n"
        "# Date and time,Wind speed (m/s),Power (kW)\n"
        "2016-06-06 18:10:00,7.5,1200.0\n"
        "2016-06-06 18:20:00,8.2,1400.0\n"
    )

    df = parse_greenbyte_csv(csv_file)
    assert "Date and time" in df.columns
    assert "Wind speed (m/s)" in df.columns
    assert "Power (kW)" in df.columns
    assert not any(c.startswith("#") for c in df.columns)
    assert len(df) == 2


def test_extract_scada_features_index_alignment():
    """Verify that extract_scada_features extracts real float values into extracted dataframe without NaN conversion."""
    import pandas as pd
    from mk.src.data.preprocessor import extract_scada_features

    df = pd.DataFrame(
        {
            "Date and time": ["2019-01-01 00:00:00", "2019-01-01 00:10:00", "2019-01-01 00:20:00"],
            "Wind speed (m/s)": [6.5, 7.0, 7.8],
            "Power (kW)": [450.0, 600.0, 780.0],
            "Rotor speed (RPM)": [11.0, 11.5, 12.0],
            "Generator RPM (RPM)": [1150.0, 1200.0, 1260.0],
            "Gear oil temperature (°C)": [52.0, 52.5, 53.0],
            "Generator bearing front temperature (°C)": [40.0, 40.5, 41.0],
            "Blade angle (pitch position) A (°)": [1.0, 1.2, 1.5],
            "Drive train acceleration (mm/ss)": [5.0, 5.2, 5.5],
        }
    )

    extracted, idx = extract_scada_features(df)
    assert len(extracted) == 3
    assert not extracted["wind_speed"].isna().any()
    assert (extracted["wind_speed"] > 0).all()
    assert extracted["power"].iloc[0] == 450.0
    assert extracted["gear_oil_temp"].iloc[0] == 52.0
    assert extracted["pitch_angle"].iloc[0] == 1.0


def test_extract_scada_features_fallbacks():
    """Verify that extract_scada_features applies fallback when gear oil or pitch angle is missing."""
    import pandas as pd
    from mk.src.data.preprocessor import extract_scada_features

    df = pd.DataFrame(
        {
            "Date and time": ["2016-06-01 00:00:00", "2016-06-01 00:10:00"],
            "Wind speed (m/s)": [14.0, 15.0],
            "Power (kW)": [1800.0, 1900.0],
            "Rotor speed (RPM)": [14.0, 15.0],
            "Generator RPM (RPM)": [1500.0, 1600.0],
            # Note: Gear oil temperature column is intentionally omitted, but Stator temperature is present
            "Stator temperature 1 (°C)": [58.0, 59.0],
            "Generator bearing front temperature (°C)": [45.0, 46.0],
            # Blade angle column is omitted
            "Drive train acceleration (mm/ss)": [8.0, 9.0],
        }
    )

    extracted, idx = extract_scada_features(df)
    assert len(extracted) == 2
    # Gear oil fallback should pick up Stator temperature
    assert extracted["gear_oil_temp"].iloc[0] == 58.0
    # Pitch angle fallback should calculate aerodynamic pitch for wind > 12: (14 - 12) * 3.5 = 7.0
    assert extracted["pitch_angle"].iloc[0] == pytest.approx(7.0, abs=0.5)



