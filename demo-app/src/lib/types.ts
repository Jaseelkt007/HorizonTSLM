export type OperationalStatus = "normal" | "warning" | "critical";

export type Subsystem =
  | "main_bearing"
  | "pitch_system"
  | "gearbox"
  | "generator"
  | "rotor"
  | "yaw"
  | "electrical";

export interface VerifiedClaim {
  claim: string;
  ok: boolean;
  evidence?: string;
}

export interface TurbineWindowRecord {
  id: string;
  anchor: string;
  horizon_h: number;
  split: string;
  state: string;
  gold: string;
  pred: string;
  score: number;
  confidence: number;
  text: string;
  claims: VerifiedClaim[];
  leadTimeMin?: number | null;
  alarmMessage?: string | null;
  durationH?: number | null;
}

export interface TurbineInfo {
  id: string;
  name: string;
  farm: string;
  turbNum: number;
  model: string;
  x: number; // Percentage coordinate on farm grid (0 to 100)
  y: number; // Percentage coordinate on farm grid (0 to 100)
  lat: number;
  lon: number;
  status: OperationalStatus;
  activePower: number; // kW
  expectedPower: number; // kW
  ratedPower: number; // kW (e.g. 2050)
  windSpeed: number; // m/s
  bearingTemp: number; // °C
  gearboxTemp: number; // °C
  generatorTemp: number; // °C
  vibrationIndex: number; // g
  activeFault: string | null;
  faultSubsystem: Subsystem | null;
  anomalyConfidence: number; // percentage, e.g. 94
  sigmaDivergence: number; // e.g. 3.4
  predictedTTF: string | null; // e.g. "48h"
  errorCode: string | null;
  diagnosticSummary: string;
  actionRecommendation: string;
  claims?: VerifiedClaim[];
  gold?: string;
  leadTimeMin?: number | null;
  windows?: TurbineWindowRecord[];
  telemetry?: {
    "24h": TelemetryPoint[];
    "7d": TelemetryPoint[];
    "30d": TelemetryPoint[];
  };
}

export interface TelemetryPoint {
  timestamp: string;
  timeLabel: string;
  activePower: number; // kW
  expectedPower: number; // kW
  powerUpperBand: number; // kW
  powerLowerBand: number; // kW
  windSpeed: number; // m/s
  bearingTemp: number; // °C
  bearingTempExpected: number; // °C
  bearingUpperBand: number; // °C
  gearboxTemp: number; // °C
  gearboxTempExpected: number; // °C
  generatorTemp: number; // °C
  vibrationIndex: number; // g
  vibrationExpected: number; // g
  capacityFactor: number; // %
  isAnomaly?: boolean;
}

export interface AlarmEvent {
  id: string;
  timestamp: string;
  turbineId: string;
  severity: "CRITICAL" | "WARNING" | "ADVISORY";
  sensorTrigger: string;
  subsystem: string;
  predictedTTF: string;
  confidence: number;
  action: string;
  active: boolean;
}

export interface FleetKPIs {
  totalFleetOutputMW: number;
  fleetAvailabilityPct: number;
  capacityFactorPct: number;
  activeAlarmsCount: number;
  criticalAlarmsCount: number;
  warningAlarmsCount: number;
  sparklineBars?: number[];
  comparisonLabel?: string;
  trendPct?: string;
  weatherForecast: {
    windSpeed: number;
    windDirection: string;
    gustSpeed: number;
    temperature: number;
    condition: string;
  };
}

export type Timeframe = "24h" | "7d" | "30d";

export type ActiveView = "overview" | "turbine" | "baseline";

export interface BenchmarkMetricRow {
  metric: string;
  heuristicBaseline: string;
  tslmModel: string;
  improvement: string;
  heuristicVal: number;
  tslmVal: number;
  description?: string;
}

export interface BenchmarkSplit {
  split: string;
  auroc: { tslm: number; baseline: number };
  ap: { tslm: number; baseline: number };
  recall_at_10far: { tslm: number; baseline: number };
  hard_f1: { tslm: number; baseline: number };
  subsystem_acc: { tslm: number; baseline: number };
  subsystem_macro_f1: { tslm: number; baseline: number };
  metricsRows: BenchmarkMetricRow[];
}
