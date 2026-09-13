import {
  TurbineInfo,
  TelemetryPoint,
  AlarmEvent,
  FleetKPIs,
  Timeframe,
  BenchmarkMetricRow,
  BenchmarkSplit,
} from "./types";
import groundedDataRaw from "./grounded-data.json";

export interface GroundedPayload {
  meta: {
    description: string;
    sources: string[];
    totalWindows: number;
  };
  farms: Record<
    string,
    {
      id: string;
      name: string;
      model: string;
      capacity: string;
      location: string;
      turbinesCount: number;
      turbines: TurbineInfo[];
      fleetPower: Record<
        Timeframe,
        Array<{
          timeLabel: string;
          actualMW: number;
          expectedMW: number;
          upperMW: number;
          lowerMW: number;
          capacityFactor: number;
          windSpeed: number;
        }>
      >;
      kpis: Record<Timeframe, FleetKPIs>;
      alarms: AlarmEvent[];
    }
  >;
  benchmarks: Record<string, BenchmarkSplit>;
}

export const GROUNDED_DATA = groundedDataRaw as unknown as GroundedPayload;

export const PLANTS = [
  {
    id: "kelmarsh",
    name: "Kelmarsh Wind Farm",
    turbinesCount: 6,
    capacity: "12.3 MW",
    location: "Northamptonshire, UK",
    model: "Senvion MM92 (2.05 MW)",
    lat: 52.41,
    lon: -0.94,
    split: "test_b",
  },
  {
    id: "penmanshiel",
    name: "Penmanshiel Wind Farm",
    turbinesCount: 14,
    capacity: "28.70 MW",
    location: "Berwickshire, UK",
    model: "Senvion MM82 (2.05 MW)",
    lat: 55.89,
    lon: -2.31,
    split: "test_a",
  },
];

/** Get all turbines for the selected wind farm */
export function getFarmTurbines(farmId: string): TurbineInfo[] {
  const farm = GROUNDED_DATA.farms[farmId] || GROUNDED_DATA.farms["kelmarsh"];
  return farm.turbines;
}

/** Get fleet KPIs for the selected farm and timeframe */
export function getFarmFleetKPIs(
  farmId: string,
  timeframe: Timeframe = "24h"
): FleetKPIs {
  const farm = GROUNDED_DATA.farms[farmId] || GROUNDED_DATA.farms["kelmarsh"];
  return farm.kpis[timeframe] || farm.kpis["24h"];
}

/** Get authentic alarm events for the selected farm */
export function getFarmAlarms(farmId: string): AlarmEvent[] {
  const farm = GROUNDED_DATA.farms[farmId] || GROUNDED_DATA.farms["kelmarsh"];
  return farm.alarms;
}

/** Get empirical benchmark metrics comparing OpenTSLM vs XGBoost */
export function getFarmBenchmarks(farmId: string): BenchmarkSplit {
  const splitKey = farmId === "penmanshiel" ? "test_a" : "test_b";
  return (
    GROUNDED_DATA.benchmarks[splitKey] || GROUNDED_DATA.benchmarks["test_b"]
  );
}

export interface AnomalyCaseStudy {
  id: string; name: string; subsystem: string; windowId: string; anchor: string;
  heuristicLeadTime: string; tslmLeadTime: string; leadTimeDelta: string;
  physicsSignatures: string[]; description: string; modelExplanation: string;
}

/** Cases are selected saved inference windows, not authored narratives. */
export function getAnomalyCaseStudies(farmId: string): AnomalyCaseStudy[] {
  return getFarmTurbines(farmId)
    .flatMap((t) => t.windows || [])
    .filter((w) => w.gold !== "none")
    .sort((a, b) => b.score - a.score)
    .slice(0, 4)
    .map((w) => ({
      id: w.id, name: `SCADA window ${w.id}`, subsystem: w.gold.replaceAll("_", " "),
      windowId: w.id, anchor: w.anchor,
      heuristicLeadTime: "Not available in source data",
      tslmLeadTime: w.leadTimeMin == null ? "No observed stop" : `${(w.leadTimeMin / 60).toFixed(1)} h observed lead`,
      leadTimeDelta: "Not computed", physicsSignatures: [],
      description: w.alarmMessage || "No alarm message recorded for this window.",
      modelExplanation: w.text,
    }));
}

/** Initial data defaults for Kelmarsh */
export const INITIAL_TURBINES: TurbineInfo[] =
  GROUNDED_DATA.farms.kelmarsh.turbines;

export const INITIAL_FLEET_KPIS: FleetKPIs =
  GROUNDED_DATA.farms.kelmarsh.kpis["24h"];

export const INITIAL_ALARMS: AlarmEvent[] =
  GROUNDED_DATA.farms.kelmarsh.alarms;

/** Return real fleet power time series grounded in the dataset for 24h, 7d, 30d */
export function generateFleetPowerSeries(
  timeframe: Timeframe,
  farmId: string = "kelmarsh",
  _tickOffset?: number | string
) {
  const farm = GROUNDED_DATA.farms[farmId] || GROUNDED_DATA.farms["kelmarsh"];
  return farm.fleetPower[timeframe] || farm.fleetPower["24h"];
}

/** Return real turbine telemetry series grounded in the dataset for 24h, 7d, 30d */
export function generateTelemetrySeries(
  turbineId: string,
  timeframe: Timeframe,
  farmId: string = "kelmarsh",
  _isLiveTick?: boolean | string,
  _tickOffset?: number
): TelemetryPoint[] {
  const turbines = getFarmTurbines(farmId);
  const turb = turbines.find((t) => t.id === turbineId) || turbines[0];
  if (turb && turb.telemetry && turb.telemetry[timeframe]) {
    return turb.telemetry[timeframe];
  }
  return turb?.telemetry?.["24h"] || [];
}

/** Get KPIs grounded for the chosen timeframe */
export function getFleetKPIsForTimeframe(
  timeframe: Timeframe,
  farmId: string = "kelmarsh"
): FleetKPIs {
  return getFarmFleetKPIs(farmId, timeframe);
}

// Backwards compatibility alias
export const BASELINE_METRICS: BenchmarkMetricRow[] =
  GROUNDED_DATA.benchmarks.test_b.metricsRows;
