"""The model's input channels: exact Greenbyte column names, units, and the two derived channels.

Strict by design: a channel that is missing from an export stays NaN and the window is dropped later. Nothing is
estimated or substituted (docs/problem-statement.md, "no claims the data cannot support"). Greenbyte's derived KPI
columns (Lost Production, Potential power, Availability, Energy Theoretical, ...) are never inputs: they are
back-calculated from the status log and would leak the label.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Channel:
    name: str  # canonical, used as the TimeNet signal name and in prompts
    column: str | None  # exact Greenbyte column; None for derived channels
    unit: str  # pint-parsable unit string
    unit_text: str  # how the unit is written in prompts
    description: str


CHANNELS: tuple[Channel, ...] = (
    Channel("wind_speed", "Wind speed (m/s)", "meter/second", "m/s", "wind speed"),
    Channel("wind_direction", "Wind direction (°)", "degree", "°", "wind direction"),
    Channel("ambient_temperature", "Nacelle ambient temperature (°C)", "degC", "°C", "nacelle ambient temperature"),
    Channel("power", "Power (kW)", "kilowatt", "kW", "active power"),
    Channel("rotor_speed", "Rotor speed (RPM)", "rpm", "rpm", "rotor speed"),
    Channel("pitch_angle", "Blade angle (pitch position) A (°)", "degree", "°", "blade pitch angle A"),
    Channel("nacelle_position", "Nacelle position (°)", "degree", "°", "nacelle position"),
    Channel("gen_bearing_front_temperature", "Generator bearing front temperature (°C)", "degC", "°C", "generator bearing front temperature"),
    Channel("gen_bearing_rear_temperature", "Generator bearing rear temperature (°C)", "degC", "°C", "generator bearing rear temperature"),
    Channel("stator_temperature", "Stator temperature 1 (°C)", "degC", "°C", "stator temperature"),
    Channel("gear_oil_temperature", "Gear oil temperature (°C)", "degC", "°C", "gear oil temperature"),
    Channel("main_bearing_temperature", "Front bearing temperature (°C)", "degC", "°C", "main (front) bearing temperature"),
    Channel("gear_oil_inlet_pressure", "Gear oil inlet pressure (bar)", "bar", "bar", "gear oil inlet pressure"),
    Channel("reactive_power", "Reactive power (kvar)", "kilovolt_ampere", "kvar", "reactive power"),  # pint has no var; VA is dimensionally identical
    Channel("grid_voltage", "Grid voltage (V)", "volt", "V", "grid voltage"),
    Channel("grid_frequency", "Grid frequency (Hz)", "hertz", "Hz", "grid frequency"),
    Channel("tower_acceleration_x", "Tower Acceleration X (mm/ss)", "millimeter/second**2", "mm/s²", "tower acceleration X"),
    Channel("power_curve_residual", None, "kilowatt", "kW", "power minus the farm power-curve expectation"),
    Channel("yaw_misalignment", None, "degree", "°", "wind direction minus nacelle position"),
)
CHANNEL_NAMES: tuple[str, ...] = tuple(c.name for c in CHANNELS)
RAW_CHANNELS: tuple[Channel, ...] = tuple(c for c in CHANNELS if c.column is not None)

STEP_MINUTES = 10


def power_curve(scada: pd.DataFrame, bin_width: float = 0.5) -> pd.Series:
    """Median power per wind-speed bin over rows where the turbine produces (power > 0).

    A per-turbine-year curve. It uses the whole file, i.e. also rows after any given anchor; that leaks nothing
    about labels, only the machine's typical behaviour, and is documented as such.
    """
    w, p = scada["Wind speed (m/s)"], scada["Power (kW)"]
    ok = w.notna() & p.notna() & (p > 0)
    bins = (w[ok] / bin_width).round() * bin_width
    curve = p[ok].groupby(bins).median()
    return curve


def extract_channels(scada: pd.DataFrame) -> pd.DataFrame:
    """Raw export -> DataFrame with exactly the columns in :data:`CHANNEL_NAMES`, on the original 10-min index."""
    out = pd.DataFrame(index=scada.index)
    for ch in RAW_CHANNELS:
        out[ch.name] = pd.to_numeric(scada[ch.column], errors="coerce") if ch.column in scada.columns else np.nan
    curve = power_curve(scada)
    if len(curve) >= 5:
        bins = (out["wind_speed"] / 0.5).round() * 0.5
        expected = bins.map(curve).astype(float)
        out["power_curve_residual"] = out["power"] - expected
    else:
        out["power_curve_residual"] = np.nan
    diff = (out["wind_direction"] - out["nacelle_position"] + 180.0) % 360.0 - 180.0
    out["yaw_misalignment"] = diff
    return out[list(CHANNEL_NAMES)]
