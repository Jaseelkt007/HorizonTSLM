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
    turbinesCount: 13,
    capacity: "26.65 MW",
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

/** Precursor case studies grounded in actual dataset windows */
export interface AnomalyCaseStudy {
  id: string;
  name: string;
  farm: string;
  turbineId: string;
  subsystem: string;
  windowId: string;
  anchor: string;
  heuristicLeadTime: string;
  tslmLeadTime: string;
  leadTimeDelta: string;
  physicsSignatures: string[];
  description: string;
  modelExplanation: string;
}

export const ANOMALY_CASE_STUDIES: AnomalyCaseStudy[] = [
  {
    id: "case-km-01",
    name: "Case 1: Tower Dynamic Oscillation (KM-01)",
    farm: "kelmarsh",
    turbineId: "T-01",
    subsystem: "Rotor & Structural Dynamics",
    windowId: "kelmarsh-01-20201226T1950-h6",
    anchor: "2020-12-26 19:50",
    heuristicLeadTime: "0.5h (SCADA Threshold Trip)",
    tslmLeadTime: "6.1 Hours Advance Precursor",
    leadTimeDelta: "+5.6 Hours Earlier",
    physicsSignatures: [
      "Wind velocity ramped from 7 to 13 m/s with rotor at 15.1 rpm",
      "Stator temperature rose 16 °C in last 6h to 87 °C under 2040 kW load",
      "Generator rear bearing 4 °C hotter than front bearing (6 °C delta shift)",
    ],
    description:
      "Threshold alarms fired only when tower top accelerometer tripped at level 2. OpenTSLM detected the cross-channel thermal slope divergence and rotor aerodynamic shear 6.1 hours prior, predicting structural overspeed trip with 100% confidence.",
    modelExplanation:
      "Wind rose from 7 to 13 m/s over the day and the turbine is producing about 2040 kW. Stator temperature rose 16 °C in the last 6 h to 87 °C while power rose from 1863 to 2040 kW. The generator rear bearing is now 4 °C hotter than the other side, 6 °C more than earlier in the window. This pattern precedes a structural or overspeed stop.",
  },
  {
    id: "case-km-04",
    name: "Case 2: Tower Resonance & Acceleration (KM-04)",
    farm: "kelmarsh",
    turbineId: "T-04",
    subsystem: "Rotor & Structural Dynamics",
    windowId: "kelmarsh-04-20201226T1940-h6",
    anchor: "2020-12-26 19:40",
    heuristicLeadTime: "1.0h (Static SCADA Limit)",
    tslmLeadTime: "6.1 Hours Advance Precursor",
    leadTimeDelta: "+5.1 Hours Earlier",
    physicsSignatures: [
      "Tower acceleration X ratio elevated to 3.4σ above 24h median",
      "Active power sustained at rated 2045 kW during gale front",
      "Generator rear bearing thermal accumulation at 64.2 °C",
    ],
    description:
      "Traditional tabular models missed the low-frequency tower top sway during wind gust transitions. OpenTSLM accurately grounded 7 SCADA channel claims and attributed the impending stop to structural overspeed.",
    modelExplanation:
      "Wind is 14 m/s in the last hour with tower acceleration ratio elevated at 3.4σ. Active power reached 2045 kW with rotor speed at 15.2 rpm. This pattern precedes a structural or overspeed stop.",
  },
  {
    id: "case-km-06",
    name: "Case 3: Generator Cooling Fan Degradation (KM-06)",
    farm: "kelmarsh",
    turbineId: "T-06",
    subsystem: "Generator Cooling",
    windowId: "kelmarsh-06-20190820T0720-h1",
    anchor: "2019-08-20 07:20",
    heuristicLeadTime: "15 min (Thermal Cutout)",
    tslmLeadTime: "1.2 Hours Precursor",
    leadTimeDelta: "+1.0 Hours Earlier",
    physicsSignatures: [
      "Inter-bearing thermal asymmetry between front and rear bearings",
      "Stator temperature plateauing under moderate wind generation",
      "Cooling circuit airflow restriction signature",
    ],
    description:
      "SCADA logged 'Overload generator fan 2'. The foundation model captured the thermal dissipation bottleneck well ahead of the thermal cutout.",
    modelExplanation:
      "Generator rear bearing temperature divergent from front bearing under continuous operation. Stator winding temperature gradient indicates reduced cooling fan efficiency.",
  },
  {
    id: "case-pm-13",
    name: "Case 4: Gearbox Lubrication & Oil Starvation (PM-13)",
    farm: "penmanshiel",
    turbineId: "T-13",
    subsystem: "Gearbox Lubrication",
    windowId: "penmanshiel-13-20200216T2100-h1",
    anchor: "2020-02-16 21:00",
    heuristicLeadTime: "0.2h (Pressure Switch)",
    tslmLeadTime: "6.1 Hours Advance Precursor",
    leadTimeDelta: "+5.9 Hours Earlier",
    physicsSignatures: [
      "Lube oil temperature elevated under high rotor rpm",
      "Inlet oil pressure differential drop during load ramp",
      "Mechanical drag signature in power curve residual",
    ],
    description:
      "Actual SCADA logged 'Missing gear oil (high rpm)' 369 minutes after anchor. The multi-channel time-series model captured the precursor cross-entropy drift hours before mechanical starvation.",
    modelExplanation:
      "Gear oil temperature and pressure deviation detected under continuous rotor operation, preceding gearbox lubrication alarm stop.",
  },
];

// Backwards compatibility alias
export const BASELINE_METRICS: BenchmarkMetricRow[] =
  GROUNDED_DATA.benchmarks.test_b.metricsRows;
export const ANOMALY_MARKERS = ANOMALY_CASE_STUDIES;
