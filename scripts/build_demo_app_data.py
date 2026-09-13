"""Build the demo-app snapshot only from exported SCADA windows and saved predictions.

The resulting JSON intentionally carries a ``source_window_id`` for every
turbine.  It contains no weather forecast, maintenance action, threshold band,
or invented alarm fields: values are either a SCADA channel, a documented
power-curve derivation, or a saved model prediction.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import pandas as pd


FARMS = {
    "kelmarsh": {"name": "Kelmarsh Wind Farm", "model": "Senvion MM92 (2.05 MW)"},
    "penmanshiel": {"name": "Penmanshiel Wind Farm", "model": "Senvion MM82 (2.05 MW)"},
}
RATED_KW = 2050.0
TELEMETRY_COLUMNS = (
    "window_id",
    "anchor",
    "power",
    "power_curve_residual",
    "wind_speed",
    "wind_direction",
    "main_bearing_temperature",
    "gear_oil_temperature",
    "stator_temperature",
    "tower_acceleration_x",
)


def number(value: float) -> float:
    return round(float(value), 2)


def status(score: float, label: str) -> str:
    if label == "none":
        return "normal"
    return "critical" if score >= 0.5 else "warning"


def compass(degrees: float) -> str:
    names = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    return names[int((degrees % 360 + 22.5) // 45) % 8]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="webapp/data/demo_data.json")
    parser.add_argument("--output", default="demo-app/src/lib/grounded-data.json")
    parser.add_argument(
        "--windows",
        nargs="+",
        default=(
            "data/interim/kelmarsh_windows.parquet",
            "data/interim/penmanshiel_windows.parquet",
        ),
        help="Interim parquet window tables used as the telemetry source.",
    )
    args = parser.parse_args()
    source = json.loads(Path(args.input).read_text())
    source_window_ids = {window["id"] for window in source["windows"]}
    parquet = pd.concat(
        [pd.read_parquet(path, columns=list(TELEMETRY_COLUMNS)) for path in args.windows],
        ignore_index=True,
    ).set_index("window_id")
    missing = source_window_ids - set(parquet.index)
    if missing:
        raise ValueError(f"{len(missing)} demo window(s) are absent from --windows")
    by_farm_turbine: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for window in source["windows"]:
        by_farm_turbine[(window["farm"], int(window["turbine"]))].append(window)

    farms: dict[str, dict] = {}
    for farm_id, meta in FARMS.items():
        turbines = []
        for (_, turbine_no), candidates in sorted(by_farm_turbine.items()):
            if _ != farm_id:
                continue
            # Prefer a positive, highest-confidence saved prediction.  The
            # selected source ID remains visible in the UI.
            window = max(candidates, key=lambda w: (w["pred"] != "none", w["score"], w["anchor"]))
            raw_window = parquet.loc[window["id"]]
            if isinstance(raw_window, pd.DataFrame):
                raise ValueError(f"Duplicate window ID in parquet input: {window['id']}")
            ch = {
                name: raw_window[name]
                for name in TELEMETRY_COLUMNS
                if name not in {"window_id", "anchor"}
            }
            anchor = pd.Timestamp(raw_window["anchor"])
            timestamps = pd.date_range(end=anchor, periods=len(ch["power"]), freq="10min")
            final = {name: values[-1] for name, values in ch.items()}
            expected = final["power"] - final["power_curve_residual"]
            telemetry = []
            for i in range(len(ch["power"])):
                power = ch["power"][i]
                residual = ch["power_curve_residual"][i]
                telemetry.append({
                    "timestamp": timestamps[i].isoformat(),
                    "timeLabel": timestamps[i].strftime("%H:%M"),
                    "activePower": number(power),
                    "expectedPower": number(power - residual),
                    "windSpeed": number(ch["wind_speed"][i]),
                    "bearingTemp": number(ch["main_bearing_temperature"][i]),
                    "gearboxTemp": number(ch["gear_oil_temperature"][i]),
                    "generatorTemp": number(ch["stator_temperature"][i]),
                    "vibrationIndex": number(ch["tower_acceleration_x"][i]),
                })
            lead = window["outcome"]["lead_time_min"]
            window_records = []
            for candidate in sorted(candidates, key=lambda w: w["anchor"], reverse=True):
                outcome = candidate["outcome"]
                window_records.append({
                    "id": candidate["id"], "anchor": candidate["anchor"], "horizon_h": candidate["horizon_h"],
                    "split": candidate["split"], "state": candidate["state"], "gold": candidate["gold"],
                    "pred": candidate["pred"], "score": candidate["score"],
                    "confidence": number(candidate["score"] * 100), "text": candidate["text"],
                    "claims": candidate["claims"], "leadTimeMin": outcome["lead_time_min"],
                    "alarmMessage": outcome["message"], "durationH": outcome["duration_h"],
                })
            turbines.append({
                "id": f"T-{turbine_no:02d}", "name": f"{farm_id[:2].upper()}-{turbine_no:02d}",
                "farm": farm_id, "turbNum": turbine_no, "model": meta["model"],
                "sourceWindowId": window["id"], "sourceAnchor": anchor.isoformat(),
                "status": status(window["score"], window["pred"]),
                "activePower": number(final["power"]), "expectedPower": number(expected),
                "ratedPower": RATED_KW, "windSpeed": number(final["wind_speed"]),
                "windDirection": compass(final["wind_direction"]), "windDirectionDegrees": number(final["wind_direction"]),
                "bearingTemp": number(final["main_bearing_temperature"]),
                "gearboxTemp": number(final["gear_oil_temperature"]),
                "generatorTemp": number(final["stator_temperature"]),
                "vibrationIndex": number(final["tower_acceleration_x"]),
                "activeFault": None if window["pred"] == "none" else window["pred"],
                "faultSubsystem": None if window["pred"] == "none" else window["pred"].split("_")[0],
                "anomalyConfidence": number(window["score"] * 100),
                "predictedTTF": None if lead is None else f"{number(lead / 60)} h observed lead",
                "diagnosticSummary": window["text"], "claims": window["claims"],
                "gold": window["gold"], "leadTimeMin": lead,
                "windows": window_records,
                "telemetry": {"24h": telemetry},
            })
        fleet = []
        for i in range(144):
            points = [t["telemetry"]["24h"][i] for t in turbines]
            actual = sum(p["activePower"] for p in points) / 1000
            expected = sum(p["expectedPower"] for p in points) / 1000
            fleet.append({"timeLabel": points[0]["timeLabel"], "actualMW": number(actual),
                          "expectedMW": number(expected),
                          "capacityFactor": number(actual / (len(turbines) * RATED_KW / 1000) * 100),
                          "windSpeed": number(sum(p["windSpeed"] for p in points) / len(points))})
        alarms = [{"id": t["sourceWindowId"], "timestamp": t["sourceAnchor"], "turbineId": t["id"],
                   "severity": "CRITICAL" if t["status"] == "critical" else "WARNING",
                   "sensorTrigger": t["activeFault"], "subsystem": t["faultSubsystem"],
                   "predictedTTF": t["predictedTTF"] or "no observed event", "confidence": t["anomalyConfidence"],
                   "active": True} for t in turbines if t["activeFault"]]
        mean_power = sum(p["actualMW"] for p in fleet) / len(fleet)
        farms[farm_id] = {"id": farm_id, "name": meta["name"], "model": meta["model"],
                          "capacity": f"{len(turbines) * 2.05:.2f} MW", "turbinesCount": len(turbines),
                          "turbines": turbines, "fleetPower": {"24h": fleet},
                          "kpis": {"24h": {"totalFleetOutputMW": number(mean_power),
                              "capacityFactorPct": number(mean_power / (len(turbines) * 2.05) * 100),
                              "activeAlarmsCount": len(alarms),
                              "criticalAlarmsCount": sum(a["severity"] == "CRITICAL" for a in alarms),
                              "warningAlarmsCount": sum(a["severity"] == "WARNING" for a in alarms),
                              "weatherForecast": {"windSpeed": number(sum(p["windSpeed"] for p in fleet) / len(fleet)),
                                                  "windDirection": compass(sum(t["windDirectionDegrees"] for t in turbines) / len(turbines))}}},
                          "alarms": alarms}
    def benchmark(split: str) -> dict:
        headline = json.loads(Path("docs/results/t1_flamingo_llama1b_evidence_rich/results.json").read_text())["results"][split]["all"]
        baseline = json.loads(Path("docs/results/xgboost_combined/results.json").read_text())["results"][split]["all"]
        metric_specs = (("AUROC", "auroc"), ("Average precision", "ap"), ("Recall @ 10% FAR", "recall_at_10far"), ("Hard F1", "hard"))
        rows = []
        for label, key in metric_specs:
            h = headline["hard"]["f1"] if key == "hard" else headline[key]
            b = baseline["hard"]["f1"] if key == "hard" else baseline[key]
            rows.append({"metric": label, "heuristicBaseline": f"{b:.3f}", "tslmModel": f"{h:.3f}",
                         "improvement": f"{(h - b) * 100:+.1f} pp", "heuristicVal": b, "tslmVal": h})
        return {"split": split, "auroc": {"tslm": headline["auroc"], "baseline": baseline["auroc"]},
                "ap": {"tslm": headline["ap"], "baseline": baseline["ap"]},
                "recall_at_10far": {"tslm": headline["recall_at_10far"], "baseline": baseline["recall_at_10far"]},
                "hard_f1": {"tslm": headline["hard"]["f1"], "baseline": baseline["hard"]["f1"]},
                "subsystem_acc": {"tslm": headline["subsystem"]["accuracy_over_positives"], "baseline": baseline["subsystem"]["accuracy_over_positives"]},
                "subsystem_macro_f1": {"tslm": headline["subsystem"]["macro_f1_over_positives"], "baseline": baseline["subsystem"]["macro_f1_over_positives"]},
                "metricsRows": rows}
    payload = {"meta": {"description": "SCADA-window and saved-model snapshot", "sources": [args.input, "docs/results/*/results.json"],
                        "totalWindows": len(source["windows"])}, "farms": farms,
               "benchmarks": {"test_a": benchmark("test_a"), "test_b": benchmark("test_b")}}
    Path(args.output).write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
