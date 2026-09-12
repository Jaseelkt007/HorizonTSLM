"""Automated tests for Penmanshiel and Kelmarsh SCADA dataset visualization module in mk/."""

import numpy as np
from src.data.schemas import (
    FAULT_CLASSES,
    SIGNAL_NAMES,
    SUBSYSTEM_CLASSES,
    WINDOW_STEPS,
    WINDOW_STEPS_12H,
)

from mk.dashboard import (
    compute_theoretical_power,
    format_tslm_explanation,
    load_all_wind_farms,
    load_static_metadata,
    load_timenet_dataset,
    load_trained_model,
    run_model_inference,
)


def test_static_metadata():
    """Verify static technical metadata for both fleets."""
    df_pen = load_static_metadata("penmanshiel")
    assert not df_pen.empty, "Penmanshiel static metadata should not be empty"
    assert len(df_pen) == 14, "Expected 14 Penmanshiel wind turbines"
    assert (df_pen["Rated power (kW)"] == 2050).all(), (
        "All Penmanshiel turbines rated 2050 kW"
    )

    df_kel = load_static_metadata("kelmarsh")
    assert not df_kel.empty, "Kelmarsh static metadata should not be empty"
    assert len(df_kel) == 6, "Expected 6 Kelmarsh wind turbines"
    assert (df_kel["Rated power (kW)"] == 2050).all(), (
        "All Kelmarsh turbines rated 2050 kW"
    )


def test_timenet_dataset_loading():
    """Verify that both Penmanshiel and Kelmarsh datasets load and parse properly."""
    df_pen, dict_pen = load_timenet_dataset("energy/penmanshiel-wind-scada")
    df_kel, dict_kel = load_timenet_dataset("energy/kelmarsh-wind-scada")

    assert len(df_pen) == 420
    assert len(df_kel) == 180
    assert len(dict_pen) == 420
    assert len(dict_kel) == 180

    # Verify column structures
    required_cols = {
        "record_id",
        "turbine_id",
        "fault_class",
        "start_time",
        "end_time",
        "rationale",
        "target",
    }
    assert required_cols.issubset(df_pen.columns)
    assert required_cols.issubset(df_kel.columns)

    # Check first telemetry window
    sample_id = df_pen["record_id"].iloc[0]
    sample_df = dict_pen[sample_id]
    assert len(sample_df) in (WINDOW_STEPS, WINDOW_STEPS_12H)
    assert list(sample_df.columns) == SIGNAL_NAMES
    assert not sample_df.isna().any().any()


def test_load_all_wind_farms_all_20_turbines():
    """Verify that all 20 turbines from both plants are present and selectable."""
    df_all, tel_all = load_all_wind_farms()
    assert len(df_all) == 600, (
        f"Expected 600 records (420 Penmanshiel + 180 Kelmarsh), got {len(df_all)}"
    )
    assert len(tel_all) == 600

    turbines = sorted(df_all["turbine_id"].unique().tolist())
    assert len(turbines) == 20, (
        f"Expected 20 unique turbines across both plants, got {len(turbines)}"
    )

    # Check Penmanshiel 14 turbines
    pen_turbines = [t for t in turbines if "Penmanshiel" in t]
    assert len(pen_turbines) == 14, (
        f"Expected 14 Penmanshiel turbines, got {len(pen_turbines)}"
    )

    # Check Kelmarsh 6 turbines
    kel_turbines = [t for t in turbines if "Kelmarsh" in t]
    assert len(kel_turbines) == 6, (
        f"Expected 6 Kelmarsh turbines, got {len(kel_turbines)}"
    )

    # Check both wind farms in metadata
    assert set(df_all["wind_farm"].unique()) == {"Penmanshiel", "Kelmarsh"}


def test_tslm_explanation_and_inference():
    """Verify 5-part TSLM report formatting and real-time model inference."""
    df_all, tel_all = load_all_wind_farms()
    sample_rec = df_all.iloc[0]
    sample_tel = tel_all[sample_rec["record_id"]]

    # Check TSLM explanation formatting
    report = format_tslm_explanation(sample_rec, sample_tel)
    assert set(report.keys()) == {
        "finding",
        "evidence",
        "cause",
        "impact",
        "action",
        "answer",
    }
    for key, val in report.items():
        assert len(val.strip()) > 0, f"Report field {key} must not be empty"

    # Check model inference
    model, meta = load_trained_model()
    if model is not None and isinstance(meta, dict):
        device_str = meta.get("device", "cpu")
        _pred_idx, pred_name, probs = run_model_inference(model, sample_tel, device_str)
        assert pred_name in FAULT_CLASSES or pred_name in SUBSYSTEM_CLASSES
        assert len(probs) in (len(FAULT_CLASSES), len(SUBSYSTEM_CLASSES))
        assert np.isclose(np.sum(probs), 1.0, atol=1e-4)


def test_theoretical_power_curve():
    """Verify aerodynamic power curve calculations."""
    ws = np.array([0.0, 2.5, 3.0, 7.0, 12.5, 18.0, 25.0, 26.0])
    p = compute_theoretical_power(ws, model="MM92")

    assert p[0] == 0.0, "Below cut-in should be 0 kW"
    assert p[1] == 0.0, "Below cut-in (2.5 m/s) should be 0 kW"
    assert p[2] == 0.0, "At cut-in (3.0 m/s) should be 0 kW"
    assert 0.0 < p[3] < 2050.0, "Between cut-in and rated should be cubic partial power"
    assert p[4] == 2050.0, "At rated speed (12.5 m/s) should produce full 2050 kW"
    assert p[5] == 2050.0, "Between rated and cut-out should remain capped at 2050 kW"
    assert p[6] == 2050.0, "At cut-out (25.0 m/s) should produce 2050 kW"
    assert p[7] == 0.0, "Above cut-out (26.0 m/s) should cut out to 0 kW"
