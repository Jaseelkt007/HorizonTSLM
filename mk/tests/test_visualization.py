"""Automated tests for the Kelmarsh SCADA dataset visualization module."""

import numpy as np
import pytest

from src.data.schemas import FAULT_CLASSES, SELECTED_SIGNALS, SIGNAL_NAMES, WINDOW_STEPS
from mk.dashboard import (
    compute_theoretical_power,
    load_static_metadata,
    load_timenet_dataset,
)


def test_static_metadata():
    """Verify static technical metadata for the Kelmarsh fleet."""
    df_static = load_static_metadata()
    assert not df_static.empty, "Static metadata should not be empty"
    assert len(df_static) == 6, "Expected 6 Kelmarsh wind turbines"
    assert "Title" in df_static.columns
    assert "Rated power (kW)" in df_static.columns
    assert (df_static["Rated power (kW)"] == 2050).all(), "All turbines should be rated at 2050 kW"


def test_timenet_dataset_loading():
    """Verify loading and signal integrity from TimeNet."""
    df_records, telemetry_dict = load_timenet_dataset()
    assert len(df_records) == 180, f"Expected 180 records, got {len(df_records)}"
    assert len(telemetry_dict) == 180, f"Expected 180 telemetry windows, got {len(telemetry_dict)}"

    # Check columns
    required_cols = {"record_id", "turbine_id", "fault_class", "start_time", "end_time", "rationale", "target"}
    assert required_cols.issubset(df_records.columns), f"Missing columns in df_records: {required_cols - set(df_records.columns)}"

    # Check fault classes
    unique_faults = set(df_records["fault_class"].unique())
    assert unique_faults == set(FAULT_CLASSES), f"Fault classes mismatch: {unique_faults}"

    # Check first telemetry window
    sample_id = df_records["record_id"].iloc[0]
    sample_df = telemetry_dict[sample_id]
    assert len(sample_df) == WINDOW_STEPS, f"Expected {WINDOW_STEPS} timesteps, got {len(sample_df)}"
    assert list(sample_df.columns) == SIGNAL_NAMES, f"Signal columns mismatch: {sample_df.columns}"

    # Verify no NaN values
    assert not sample_df.isna().any().any(), "Telemetry window should have no NaN values"


def test_theoretical_power_curve():
    """Verify aerodynamic power curve calculations."""
    ws = np.array([0.0, 2.5, 3.0, 7.0, 12.5, 18.0, 25.0, 26.0])
    p = compute_theoretical_power(ws)

    assert p[0] == 0.0, "Below cut-in should be 0 kW"
    assert p[1] == 0.0, "Below cut-in (2.5 m/s) should be 0 kW"
    assert p[2] == 0.0, "At cut-in (3.0 m/s) should be 0 kW"
    assert 0.0 < p[3] < 2050.0, "Between cut-in and rated should be cubic partial power"
    assert p[4] == 2050.0, "At rated speed (12.5 m/s) should produce full 2050 kW"
    assert p[5] == 2050.0, "Between rated and cut-out should remain capped at 2050 kW"
    assert p[6] == 2050.0, "At cut-out (25.0 m/s) should produce 2050 kW"
    assert p[7] == 0.0, "Above cut-out (26.0 m/s) should cut out to 0 kW"
