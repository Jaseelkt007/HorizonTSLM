"""Rule-based evidence text for a 24 h window (docs/problem-statement.md §7, "how training targets are produced").

Every sentence is derived from the window's raw values only — nothing from after the anchor and nothing from the
alarm log except the final class name, which is the training label anyway. The text is the reasoning the model is
trained to write *before* its ``Answer:`` line; the same facts are returned as numbers so generated text can later be
checked against them.

    facts = extract_facts(series)                       # {name: value} numeric facts
    text  = evidence_text(series, label)                # paragraph ending in "Answer: ..."
"""

from __future__ import annotations

from typing import Any

import numpy as np

from turbine_tslm.data.channels import STEP_MINUTES
from turbine_tslm.data.prompts import answer_label

STEPS_PER_HOUR = 60 // STEP_MINUTES
CUT_IN_WIND = 3.5
THERMAL = {
    "gen_bearing_front_temperature": "generator front bearing",
    "gen_bearing_rear_temperature": "generator rear bearing",
    "stator_temperature": "stator",
    "gear_oil_temperature": "gear oil",
    "main_bearing_temperature": "main bearing",
}
CONCLUSION = {
    "generator_cooling": "This pattern precedes a generator cooling stop.",
    "gearbox_lubrication": "This pattern precedes a gearbox lubrication stop.",
    "pitch_system": "This pattern precedes a pitch system stop.",
    "structural_overspeed": "This pattern precedes a structural or overspeed stop.",
    "converter_grid": "This pattern precedes a converter or grid stop.",
    "brake_hydraulics": "This pattern precedes a brake or hydraulics stop.",
    "yaw_cable": "This pattern precedes a yaw or cable stop.",
    "sensor_comms": "This pattern precedes a sensor or communication stop.",
}


def _mean(v: np.ndarray, a: int, b: int) -> float:
    seg = v[a:b]
    return float(np.nanmean(seg)) if np.isfinite(seg).any() else float("nan")


def _h(hours: float) -> int:
    return round(hours * STEPS_PER_HOUR)


def extract_facts(series: dict[str, np.ndarray]) -> dict[str, Any]:
    """Numeric facts from the raw window (144 steps). Keys are stable; values may be NaN when a channel is flat."""
    s = {k: np.asarray(v, dtype=float) for k, v in series.items()}
    n = len(next(iter(s.values())))
    last1 = slice(n - _h(1), n)
    f: dict[str, Any] = {}

    w = s["wind_speed"]
    f["wind_first6h"] = _mean(w, 0, _h(6))
    f["wind_last6h"] = _mean(w, n - _h(6), n)
    f["wind_last1h"] = _mean(w, last1.start, n)
    f["wind_mean"] = float(np.nanmean(w))
    f["wind_max"] = float(np.nanmax(w))
    p = s["power"]
    f["power_last1h"] = _mean(p, last1.start, n)
    f["power_first6h"] = _mean(p, 0, _h(6))
    f["power_6h_ago"] = _mean(p, n - _h(7), n - _h(6))
    f["power_max"] = float(np.nanmax(p))
    f["producing"] = f["power_last1h"] > 50
    f["residual_last3h"] = _mean(s["power_curve_residual"], n - _h(3), n)

    for name in THERMAL:
        v = s[name]
        now = _mean(v, last1.start, n)
        f[f"{name}_now"] = now
        f[f"{name}_delta3h"] = now - _mean(v, n - _h(4), n - _h(3))
        f[f"{name}_delta6h"] = now - _mean(v, n - _h(7), n - _h(6))
        f[f"{name}_at_max"] = bool(now >= np.nanmax(v) - 1.0)
    f["ambient_now"] = _mean(s["ambient_temperature"], last1.start, n)
    rear, front = s["gen_bearing_rear_temperature"], s["gen_bearing_front_temperature"]
    asym = rear - front
    f["bearing_asym_now"] = _mean(asym, last1.start, n)
    f["bearing_asym_mean"] = float(np.nanmean(asym))

    op = s["gear_oil_inlet_pressure"]
    f["oil_pressure_now"] = _mean(op, last1.start, n)
    f["oil_pressure_6h_ago"] = _mean(op, n - _h(7), n - _h(6))
    f["oil_pressure_delta6h"] = f["oil_pressure_now"] - f["oil_pressure_6h_ago"]
    f["oil_pressure_mean"] = float(np.nanmean(op))
    f["oil_pressure_std"] = float(np.nanstd(op))

    f["pitch_last1h"] = _mean(s["pitch_angle"], last1.start, n)
    f["rotor_rpm_last1h"] = _mean(s["rotor_speed"], last1.start, n)
    f["rotor_rpm_max"] = float(np.nanmax(s["rotor_speed"]))

    acc = s["tower_acceleration_x"]
    med = float(np.nanmedian(acc))
    f["tower_acc_last1h"] = _mean(acc, last1.start, n)
    f["tower_acc_median"] = med
    f["tower_acc_ratio"] = f["tower_acc_last1h"] / med if med > 1e-6 else float("nan")
    f["tower_acc_max"] = float(np.nanmax(acc))

    gv, gf = s["grid_voltage"], s["grid_frequency"]
    f["grid_voltage_max_step"] = float(np.nanmax(np.abs(np.diff(gv)))) if n > 1 else 0.0
    f["grid_voltage_now"] = _mean(gv, last1.start, n)
    f["grid_freq_max_dev"] = float(np.nanmax(np.abs(gf - 50.0)))
    f["yaw_misalignment_last1h"] = _mean(s["yaw_misalignment"], last1.start, n)

    # generic excursions: channels whose last hour sits > 2.5 window-std from the window mean
    exc = {}
    for name, v in s.items():
        sd = float(np.nanstd(v))
        if sd > 1e-6:
            z = (_mean(v, last1.start, n) - float(np.nanmean(v))) / sd
            if abs(z) >= 2.5:
                exc[name] = round(float(z), 1)
    f["excursions"] = exc
    return f


def _fmt(x: float, nd: int = 0) -> str:
    return f"{x:.{nd}f}"


# thresholds from the Penmanshiel window tables (docs/session-handoff.md, 13 Sep): 6 h temperature deltas correlate
# 0.6 with the 6 h power change (5–95 % at steady load ±14 °C), rear-front asymmetry change 95 % = 5.3 °C, tower
# acceleration last-hour/median 90 % = 1.7 / 99 % = 5.9, grid voltage 10-min step 99 % = 8.6 V, frequency deviation
# 99 % = 0.18 Hz, |yaw error| 90 % = 9° / 99 % = 60°, gear-oil pressure (recorded units, 100–280 while producing).
STEADY_LOAD_KW = 200
TEMP_RISE_STEADY = 6.0
TEMP_RISE_LOADED = 15.0
ASYM_CHANGE = 4.0
OIL_REL_DROP = 0.25
TOWER_RATIO = 2.0
GRID_V_STEP = 8.0
GRID_F_DEV = 0.18
YAW_ERR = 25.0
HIGH_WIND = 12.0

RELEVANT = {  # which evidence tags justify a class-specific conclusion
    "generator_cooling": {
        "gen_bearing_front_temperature",
        "gen_bearing_rear_temperature",
        "stator_temperature",
        "asym",
    },
    "gearbox_lubrication": {
        "gear_oil_temperature",
        "oil_pressure",
        "main_bearing_temperature",
    },
    "structural_overspeed": {"tower", "rotor"},
    "pitch_system": {"pitch", "residual"},
    "converter_grid": {"grid_v", "grid_f", "reactive_power"},
    "yaw_cable": {"yaw"},
}


def evidence_sentences(f: dict[str, Any]) -> list[tuple[str, str]]:
    """(tag, sentence) pairs, most important first. Empty list = nothing unusual in the window."""
    out: list[tuple[str, str]] = []
    dP = f["power_last1h"] - f["power_6h_ago"]
    steady = abs(dP) < STEADY_LOAD_KW
    load = (
        "at steady load"
        if steady
        else f"while power {'rose' if dP > 0 else 'fell'} from {_fmt(f['power_6h_ago'])} to {_fmt(f['power_last1h'])} kW"
    )
    ramps = []
    for name, label in THERMAL.items():
        d = f[f"{name}_delta6h"]
        if np.isfinite(d) and d >= (
            TEMP_RISE_STEADY if steady or dP < 0 else TEMP_RISE_LOADED
        ):
            ramps.append((d, name, label))
    ramps.sort(reverse=True)
    for d, name, label in ramps[:2]:
        sent = f"{label.capitalize()} temperature rose {_fmt(d)} °C in the last 6 h to {_fmt(f[f'{name}_now'])} °C {load}"
        if f[f"{name}_at_max"]:
            sent += ", its 24 h maximum"
        out.append((name, sent + "."))
    asym_d = f["bearing_asym_now"] - f["bearing_asym_mean"]
    if np.isfinite(asym_d) and abs(asym_d) >= ASYM_CHANGE:
        hot = "rear" if f["bearing_asym_now"] > 0 else "front"
        out.append(
            (
                "asym",
                (
                    f"The generator {hot} bearing is now {_fmt(abs(f['bearing_asym_now']))} °C hotter than the other side, "
                    f"{_fmt(abs(asym_d))} °C {'more' if asym_d * f['bearing_asym_now'] > 0 else 'less'} than earlier in the window."
                ),
            )
        )
    p0 = f["oil_pressure_6h_ago"]
    if f["producing"] and f["power_6h_ago"] > 50 and np.isfinite(p0) and p0 > 1e-6:
        rel = (f["oil_pressure_now"] - p0) / p0
        if rel <= -OIL_REL_DROP:
            out.append(
                (
                    "oil_pressure",
                    f"Gear oil inlet pressure fell {_fmt(-rel * 100)} % over 6 h (from {_fmt(p0)} to {_fmt(f['oil_pressure_now'])}) {load}.",
                )
            )
    if (
        np.isfinite(f["tower_acc_ratio"])
        and f["tower_acc_ratio"] >= TOWER_RATIO
        and f["tower_acc_last1h"] > 5
    ):
        out.append(
            (
                "tower",
                f"Tower acceleration X is {_fmt(f['tower_acc_last1h'])} mm/s² in the last hour, {_fmt(f['tower_acc_ratio'], 1)}× its 24 h median.",
            )
        )
    if f["producing"] and (
        f["wind_last1h"] >= HIGH_WIND
        or f["rotor_rpm_last1h"] >= f["rotor_rpm_max"] - 0.3
    ):
        out.append(
            (
                "rotor",
                (
                    f"Wind is {_fmt(f['wind_last1h'])} m/s in the last hour (24 h maximum {_fmt(f['wind_max'])} m/s) with the rotor at "
                    f"{_fmt(f['rotor_rpm_last1h'], 1)} rpm{' (its 24 h maximum)' if f['rotor_rpm_last1h'] >= f['rotor_rpm_max'] - 0.3 else ''} "
                    f"and power at {_fmt(f['power_last1h'])} kW."
                ),
            )
        )
    if f["grid_voltage_max_step"] >= GRID_V_STEP:
        out.append(
            (
                "grid_v",
                f"Grid voltage stepped by {_fmt(f['grid_voltage_max_step'])} V within 10 minutes during the window.",
            )
        )
    if f["grid_freq_max_dev"] >= GRID_F_DEV:
        out.append(
            (
                "grid_f",
                f"Grid frequency deviated up to {_fmt(f['grid_freq_max_dev'], 2)} Hz from 50 Hz.",
            )
        )
    if (
        f["wind_last1h"] > CUT_IN_WIND + 1
        and f["rotor_rpm_last1h"] < 2
        and f["pitch_last1h"] > 60
    ):
        out.append(
            (
                "pitch",
                f"Blades are feathered at {_fmt(f['pitch_last1h'])}° with the rotor stopped although wind is {_fmt(f['wind_last1h'])} m/s.",
            )
        )
    if (
        f["producing"]
        and np.isfinite(f["residual_last3h"])
        and f["residual_last3h"] <= -150
        and f["wind_last1h"] > CUT_IN_WIND
    ):
        out.append(
            (
                "residual",
                f"Power is {_fmt(-f['residual_last3h'])} kW below the farm power curve for this wind over the last 3 h.",
            )
        )
    if abs(f["yaw_misalignment_last1h"]) >= YAW_ERR:
        out.append(
            (
                "yaw",
                f"Nacelle is {_fmt(abs(f['yaw_misalignment_last1h']))}° off the wind direction in the last hour.",
            )
        )
    covered = set(THERMAL) | {
        "gear_oil_inlet_pressure",
        "tower_acceleration_x",
        "grid_voltage",
        "grid_frequency",
        "pitch_angle",
        "rotor_speed",
        "power_curve_residual",
        "yaw_misalignment",
        "wind_speed",
        "power",
        "wind_direction",
        "nacelle_position",
    }
    for name, z in sorted(f["excursions"].items(), key=lambda kv: -abs(kv[1]))[:1]:
        if name not in covered:
            out.append(
                (
                    name,
                    f"{name.replace('_', ' ').capitalize()} sits {abs(z)} standard deviations {'above' if z > 0 else 'below'} its 24 h mean in the last hour.",
                )
            )
    return out


def state_sentence(f: dict[str, Any]) -> str:
    w0, w1 = f["wind_first6h"], f["wind_last6h"]
    if np.isfinite(w0) and np.isfinite(w1) and abs(w1 - w0) >= 2:
        wind = f"Wind {'rose' if w1 > w0 else 'fell'} from {_fmt(w0)} to {_fmt(w1)} m/s over the day"
    else:
        wind = f"Wind is steady around {_fmt(f['wind_mean'])} m/s"
    if f["producing"]:
        power = f"the turbine is producing about {_fmt(f['power_last1h'])} kW"
    elif f["wind_last1h"] < CUT_IN_WIND:
        power = "the turbine is idle below cut-in wind"
    else:
        power = "the turbine is not producing"
    return f"{wind} and {power}."


def evidence_text(
    series: dict[str, np.ndarray], label: str, max_sentences: int = 3
) -> str:
    """Reason-first answer: state, up to ``max_sentences`` evidence sentences, conclusion, then the scored line.

    The class-specific conclusion is only written when at least one sentence is relevant to that class
    (``RELEVANT``); otherwise the text says honestly that no specific precursor is visible.
    """
    f = extract_facts(series)
    tagged = evidence_sentences(f)[:max_sentences]
    parts = [state_sentence(f)] + [sent for _, sent in tagged]
    tags = {tag for tag, _ in tagged}
    if label == "none":
        parts.append(
            "No sign of a developing fault."
            if not tagged
            else "Nothing here points to an imminent fault stop."
        )
    elif tags & RELEVANT.get(label, set()):
        parts.append(
            CONCLUSION.get(
                label, f"This pattern precedes a {label.replace('_', ' ')} stop."
            )
        )
    else:
        parts.append(
            f"No specific precursor for it is visible in these signals, but a {label.replace('_', ' ')} stop follows."
        )
    return " ".join(parts) + "\n" + answer_label(label)
