"""Automated unit tests for the dedicated SCADA Data Inspection Visualizer in mk/."""

import numpy as np
import pandas as pd
import pytest

from mk.data_inspection import (
    SIGNAL_THRESHOLDS,
    compute_fleet_average_baseline,
    compute_theoretical_power,
    find_concurrent_sister_window,
    find_matching_healthy_baseline,
    load_all_wind_farms,
    load_static_metadata,
    parse_event_annotations,
)
from mk.src.data.schemas import (
    FAULT_CLASSES,
    SIGNAL_NAMES,
    WINDOW_STEPS,
    WINDOW_STEPS_12H,
)


@pytest.fixture(scope="module")
def farm_data():
    """Loads and caches both wind farms once for the test module."""
    df_all_records, telemetry_dict = load_all_wind_farms()
    return df_all_records, telemetry_dict


def test_dataset_inventory(farm_data):
    """Verify all 20 turbines and 600 telemetry records are present."""
    df_all, tel_dict = farm_data
    assert len(df_all) == 600
    assert len(tel_dict) == 600

    turbines = sorted(df_all["turbine_id"].unique().tolist())
    assert len(turbines) == 20
    assert any("Penmanshiel" in t for t in turbines)
    assert any("Kelmarsh" in t for t in turbines)


def test_date_and_time_ranges(farm_data):
    """Verify date ranges, window length, and 10-minute cadence."""
    df_all, tel_dict = farm_data

    # Check date boundaries
    min_time = df_all["start_time"].min()
    max_time = df_all["start_time"].max()
    assert min_time < max_time

    sample_rec = df_all.iloc[0]
    sample_tel = tel_dict[sample_rec["record_id"]]

    # Verify timesteps
    assert len(sample_tel) in (WINDOW_STEPS, WINDOW_STEPS_12H)
    assert list(sample_tel.columns) == SIGNAL_NAMES
    diff_min = (sample_tel.index[1] - sample_tel.index[0]).total_seconds() / 60
    assert diff_min == 10.0


def test_scada_event_annotations(farm_data):
    """Verify SCADA event annotations, alarms, rationale, and recommended actions across all classes."""
    df_all, tel_dict = farm_data

    for fc in FAULT_CLASSES:
        subset = df_all[df_all["fault_class"] == fc]
        assert not subset.empty, f"No records found for class {fc}"
        rec = subset.iloc[0]
        tel = tel_dict[rec["record_id"]]

        ann = parse_event_annotations(rec, tel)
        assert ann["fault_class"] == fc
        assert "action" in ann and len(ann["action"]) > 0
        assert "alarms" in ann and len(ann["alarms"]) > 0

        # Check alarm fields
        for alarm in ann["alarms"]:
            assert "timestamp" in alarm
            assert "severity" in alarm
            assert "code" in alarm
            assert "message" in alarm

        if fc != "Normal Operation":
            assert any(a["severity"] in ["WARNING", "ALARM", "TRIP / OUTAGE"] for a in ann["alarms"])


def test_turbine_to_turbine_concurrent_pairing(farm_data):
    """Verify concurrent sister turbine pairing and residual calculation."""
    df_all, tel_dict = farm_data

    # Pick Kelmarsh 1
    rec_a = df_all[df_all["turbine_id"] == "Kelmarsh 1"].iloc[0]
    tel_a = tel_dict[rec_a["record_id"]]

    # Find sister turbine Kelmarsh 2
    sister_rid = find_concurrent_sister_window(df_all, rec_a, "Kelmarsh 2")
    assert sister_rid is not None
    assert sister_rid in tel_dict

    tel_b = tel_dict[sister_rid]
    rec_b = df_all[df_all["record_id"] == sister_rid].iloc[0]
    assert rec_b["turbine_id"] == "Kelmarsh 2"

    # Compute residual
    for sig in ["wind_speed", "power", "rotor_speed", "gear_oil_temp"]:
        res = tel_a[sig].values - tel_b[sig].values
        assert len(res) in (WINDOW_STEPS, WINDOW_STEPS_12H)
        assert not np.isnan(res).any()


def test_matching_healthy_baseline(farm_data):
    """Verify finding a healthy baseline window closely matching the wind speed."""
    df_all, tel_dict = farm_data

    # Test on a fault window
    fault_rec = df_all[df_all["fault_class"] == "Gearbox Overheating"].iloc[0]
    fault_tel = tel_dict[fault_rec["record_id"]]

    healthy_rid, healthy_tel = find_matching_healthy_baseline(df_all, tel_dict, fault_rec, fault_tel)
    assert healthy_rid is not None
    healthy_rec = df_all[df_all["record_id"] == healthy_rid].iloc[0]
    assert healthy_rec["fault_class"] == "Normal Operation"

    # Residuals should be valid
    residual_power = fault_tel["power"].values - healthy_tel["power"].values
    assert len(residual_power) in (WINDOW_STEPS, WINDOW_STEPS_12H)
    assert not np.isnan(residual_power).any()


def test_fleet_average_baseline(farm_data):
    """Verify farm-wide fleet average baseline and variance envelope."""
    df_all, tel_dict = farm_data
    sample_rec = df_all.iloc[0]

    mean_df, std_df = compute_fleet_average_baseline(df_all, tel_dict, sample_rec)
    assert mean_df is not None
    assert std_df is not None
    assert "wind_speed" in mean_df.columns
    assert "power" in mean_df.columns
    assert (mean_df["wind_speed"] >= 0).all()
    assert (std_df["wind_speed"] >= 0).all()


def test_theoretical_power_curve():
    """Verify Senvion MM82 / MM92 power curve calculations."""
    wind_speeds = np.array([0.0, 2.0, 3.0, 6.0, 10.0, 12.5, 15.0, 24.0, 26.0])

    p_mm92 = compute_theoretical_power(wind_speeds, model="MM92")
    assert p_mm92[0] == 0.0  # Calm
    assert p_mm92[1] == 0.0  # Below cut-in (3 m/s)
    assert p_mm92[2] >= 0.0  # Cut-in
    assert p_mm92[3] < p_mm92[4]  # Ascending power region
    assert p_mm92[5] == 2050.0  # Rated power
    assert p_mm92[6] == 2050.0  # Plateau
    assert p_mm92[7] == 2050.0  # Near cut-out
    assert p_mm92[8] == 0.0  # Above cut-out (25 m/s)
