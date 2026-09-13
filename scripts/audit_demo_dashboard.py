"""Verify that the dashboard snapshots are reproducible from committed sources.

This is deliberately an offline check: the dashboard must not need a live
service to prove where a value originated.  It verifies the webapp's 160
curated windows against ``data/interim/*.parquet`` and verifies the newer
``demo-app`` snapshot against that curated export and saved result files.

Run:
    .venv/bin/python scripts/audit_demo_dashboard.py
"""

from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
WEBAPP = ROOT / "webapp" / "data" / "demo_data.json"
DEMO_APP = ROOT / "demo-app" / "src" / "lib" / "grounded-data.json"
PREDICTIONS = ROOT / "docs" / "results" / "t1_flamingo_llama1b_evidence_rich" / "predictions.jsonl.gz"
RESULTS = ROOT / "docs" / "results"
RATED_KW = 2050.0


def fail(message: str) -> None:
    raise AssertionError(message)


def rounded(value: float) -> float:
    return round(float(value), 2)


def equal(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        fail(f"{label}: got {actual!r}, expected {expected!r}")


def close(actual: float, expected: float, label: str) -> None:
    if not np.isclose(float(actual), float(expected), atol=0.005, rtol=0):
        fail(f"{label}: got {actual!r}, expected {expected!r}")


def load_windows() -> pd.DataFrame:
    frames = [pd.read_parquet(p) for p in sorted(INTERIM.glob("*_windows.parquet"))]
    if not frames:
        fail(f"No window tables found in {INTERIM}")
    out = pd.concat(frames, ignore_index=True)
    if out.window_id.duplicated().any():
        fail("Duplicate window_id in interim tables")
    return out.set_index("window_id")


def load_predictions() -> dict[str, dict]:
    with gzip.open(PREDICTIONS, "rt", encoding="utf-8") as handle:
        rows = (json.loads(line) for line in handle if line.strip())
        return {
            row["window_id"]: row
            for row in rows
            if row.get("task", "t1") == "t1" and row["split"] in {"test_a", "test_b"}
        }


def audit_curated_export(source: dict, table: pd.DataFrame, predictions: dict[str, dict]) -> None:
    ids = [w["id"] for w in source["windows"]]
    if len(ids) != len(set(ids)):
        fail("webapp/data/demo_data.json contains duplicate window ids")
    missing = set(ids) - set(table.index)
    if missing:
        fail(f"Curated windows missing from interim tables: {sorted(missing)[:3]}")
    missing_predictions = set(ids) - set(predictions)
    if missing_predictions:
        fail(f"Curated windows missing from saved predictions: {sorted(missing_predictions)[:3]}")

    for window in source["windows"]:
        row = table.loc[window["id"]]
        prediction = predictions[window["id"]]
        for key in ("farm", "split"):
            equal(window[key], row[key], f"{window['id']} {key}")
        for key in ("turbine", "horizon_h"):
            equal(window[key], int(row[key]), f"{window['id']} {key}")
        equal(window["anchor"], pd.Timestamp(row["anchor"]).strftime("%Y-%m-%d %H:%M"), f"{window['id']} anchor")
        equal(window["state"], row["state_at_anchor"], f"{window['id']} state")
        equal(window["gold"], prediction["gold"], f"{window['id']} gold prediction")
        equal(window["pred"], prediction["label"], f"{window['id']} prediction")
        close(window["score"], round(float(prediction["score"]), 3), f"{window['id']} score")

        outcome = window["outcome"]
        equal(outcome["message"], None if pd.isna(row.next_event_message) else row.next_event_message, f"{window['id']} outcome message")
        expected_lead = None if pd.isna(row.lead_time_min) else round(float(row.lead_time_min))
        equal(outcome["lead_time_min"], expected_lead, f"{window['id']} outcome lead")
        expected_duration = None if pd.isna(row.next_event_duration_h) else round(float(row.next_event_duration_h), 1)
        equal(outcome["duration_h"], expected_duration, f"{window['id']} outcome duration")

        for channel, values in window["channels"].items():
            expected = np.asarray(row[channel], dtype=float)
            actual = np.asarray(values, dtype=float)
            if actual.shape != (144,) or expected.shape != (144,):
                fail(f"{window['id']} {channel}: expected a 144-step series")
            if not np.allclose(actual, np.round(expected, 2), atol=0.005, rtol=0, equal_nan=True):
                fail(f"{window['id']} {channel}: curated series differs from interim source")


def selected_windows(source: dict) -> dict[tuple[str, int], dict]:
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for window in source["windows"]:
        grouped[(window["farm"], int(window["turbine"]))].append(window)
    return {
        key: max(values, key=lambda w: (w["pred"] != "none", w["score"], w["anchor"]))
        for key, values in grouped.items()
    }


def audit_operator_snapshot(source: dict, dashboard: dict, table: pd.DataFrame) -> None:
    selected = selected_windows(source)
    for farm_id, farm in dashboard["farms"].items():
        turbines = farm["turbines"]
        expected_turbines = [selected[(farm_id, n)] for n in sorted(n for f, n in selected if f == farm_id)]
        equal(len(turbines), len(expected_turbines), f"{farm_id} turbine count")
        for turbine, window in zip(turbines, expected_turbines, strict=True):
            prefix = f"{farm_id}/{turbine['id']}"
            raw_window = table.loc[window["id"]]
            equal(turbine["sourceWindowId"], window["id"], f"{prefix} source window")
            # UI snapshots may serialize the same UTC timestamp either as an
            # ISO string or as the compact display string used by webapp.
            source_anchor = pd.Timestamp(turbine["sourceAnchor"])
            expected_anchor = pd.Timestamp(window["anchor"])
            if expected_anchor.tzinfo is None:
                expected_anchor = expected_anchor.tz_localize("UTC")
            equal(source_anchor, expected_anchor, f"{prefix} source anchor")
            final = {name: values[-1] for name, values in window["channels"].items()}
            for output, channel in (("activePower", "power"), ("windSpeed", "wind_speed"),
                                    ("bearingTemp", "main_bearing_temperature"),
                                    ("gearboxTemp", "gear_oil_temperature"),
                                    ("generatorTemp", "stator_temperature"),
                                    ("vibrationIndex", "tower_acceleration_x")):
                close(turbine[output], rounded(final[channel]), f"{prefix} {output}")
            close(turbine["expectedPower"], rounded(raw_window["power"][-1] - raw_window["power_curve_residual"][-1]), f"{prefix} expected power")
            equal(turbine["anomalyConfidence"], rounded(window["score"] * 100), f"{prefix} confidence")
            expected_ttf = None if window["outcome"]["lead_time_min"] is None else f"{rounded(window['outcome']['lead_time_min'] / 60)} h observed lead"
            equal(turbine["predictedTTF"], expected_ttf, f"{prefix} lead time")
            telemetry = turbine["telemetry"]["24h"]
            equal(len(telemetry), 144, f"{prefix} telemetry length")
            for i, point in enumerate(telemetry):
                for output, channel in (("activePower", "power"), ("windSpeed", "wind_speed"),
                                        ("bearingTemp", "main_bearing_temperature"), ("gearboxTemp", "gear_oil_temperature"),
                                        ("generatorTemp", "stator_temperature"), ("vibrationIndex", "tower_acceleration_x")):
                    close(point[output], rounded(window["channels"][channel][i]), f"{prefix} sample {i} {output}")
                close(point["expectedPower"], rounded(raw_window["power"][i] - raw_window["power_curve_residual"][i]), f"{prefix} sample {i} expected power")

        fleet = farm["fleetPower"]["24h"]
        equal(len(fleet), 144, f"{farm_id} fleet series length")
        for i, point in enumerate(fleet):
            values = [t["telemetry"]["24h"][i] for t in turbines]
            close(point["actualMW"], rounded(sum(p["activePower"] for p in values) / 1000), f"{farm_id} fleet {i} actual")
            close(point["expectedMW"], rounded(sum(p["expectedPower"] for p in values) / 1000), f"{farm_id} fleet {i} expected")
            close(point["windSpeed"], rounded(sum(p["windSpeed"] for p in values) / len(values)), f"{farm_id} fleet {i} wind")
            # The generator computes this before rounding the displayed MW total.
            capacity_factor = (sum(p["activePower"] for p in values) / 1000) / (len(turbines) * RATED_KW / 1000) * 100
            close(point["capacityFactor"], rounded(capacity_factor), f"{farm_id} fleet {i} capacity factor")

        active = [t for t in turbines if t["activeFault"]]
        equal(farm["kpis"]["24h"]["activeAlarmsCount"], len(active), f"{farm_id} active alarm count")
        equal(len(farm["alarms"]), len(active), f"{farm_id} alarm rows")


def audit_benchmarks(dashboard: dict) -> None:
    headline = json.loads((RESULTS / "t1_flamingo_llama1b_evidence_rich" / "results.json").read_text())["results"]
    baseline = json.loads((RESULTS / "xgboost_combined" / "results.json").read_text())["results"]
    for split in ("test_a", "test_b"):
        shown = dashboard["benchmarks"][split]
        for field in ("auroc", "ap", "recall_at_10far"):
            close(shown[field]["tslm"], headline[split]["all"][field], f"{split} headline {field}")
            close(shown[field]["baseline"], baseline[split]["all"][field], f"{split} baseline {field}")


def main() -> int:
    source = json.loads(WEBAPP.read_text())
    dashboard = json.loads(DEMO_APP.read_text())
    table = load_windows()
    predictions = load_predictions()
    audit_curated_export(source, table, predictions)
    audit_operator_snapshot(source, dashboard, table)
    audit_benchmarks(dashboard)
    print(f"PASS: {len(source['windows'])} dashboard windows match interim tables; operator snapshot and benchmarks reconcile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
