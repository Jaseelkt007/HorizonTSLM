/** Domain impact calculations aligning with wind farm operator priorities:
 * - Minimizing Levelized Cost of Energy (LCOE)
 * - Avoiding unscheduled downtime and expensive emergency mobilization (£2,500+)
 * - Tracking Energetic Availability and MWh at risk
 * - Prescriptive action recommendations (Sense -> Reason -> Act)
 */

import type { ImpactAssessment, Outcome, PrescriptiveAction, UrgencyLevel } from "./types";

export const RATED_POWER_KW = 2050; // Senvion MM82 / MM92 rated power: 2.05 MW
export const WHOLESALE_GBP_PER_MWH = 85; // UK wholesale benchmark
export const EMERGENCY_CALLOUT_COST_GBP = 2500; // Emergency out-of-hours technician / mobilization cost
export const PLANNED_ACTION_COST_GBP = 250; // Planned day-shift maintenance / remote de-rate

const DEFAULT_DOWNTIME_HOURS: Record<string, number> = {
  generator_cooling: 1.2,
  gearbox_lubrication: 2.0,
  pitch_system: 0.8,
  converter_grid: 0.6,
  structural_overspeed: 0.4,
  brake_hydraulics: 0.8,
  yaw_cable: 0.5,
  sensor_comms: 0.3,
  none: 0.0,
};

const PRESCRIPTIVE_PLAYBOOK: Record<string, { title: string; rationale: string; steps: string[] }> = {
  generator_cooling: {
    title: "Remote De-rate to 1.2 MW & Fan Contactor Inspection",
    rationale:
      "Drivetrain heat dissipation is lagging load increase. De-rating active power to 1.2 MW reduces heat load by ~45%, capping rear bearing and stator temperature below the 85 °C controller trip threshold.",
    steps: [
      "Issue remote active power setpoint: 1,200 kW (derate -41%)",
      "Command auxiliary fan 1 & 2 forced run sequence",
      "Schedule visual inspection of radiator ducting and cooling circuit breaker during next shift",
      "Alert control room if rear/front bearing asymmetry exceeds 12 °C",
    ],
  },
  structural_overspeed: {
    title: "Apply +2° Pitch Trim & Tower Resonance Damping Check",
    rationale:
      "High nacelle/tower acceleration surges indicate impending aerodynamic oscillation or gust-induced overspeed. Adding positive pitch bias sheds rotor thrust without initiating an emergency mechanical brake trip.",
    steps: [
      "Trim blade pitch offset by +2.0° across axes A/B/C",
      "Cap maximum rotor speed setpoint to 14.8 RPM",
      "Monitor tower acceleration X RMS (< 50 mm/s²)",
      "If wind gusts exceed 20 m/s, execute staged aerodynamic feathering",
    ],
  },
  gearbox_lubrication: {
    title: "Force Auxiliary Lube Pump Run & Filter DP Verification",
    rationale:
      "Oil inlet pressure sag under load indicates suction line restriction or filter clogging. Forcing the auxiliary pump restores hydraulic head pressure to critical bearing journals.",
    steps: [
      "Trigger auxiliary gear oil pump continuous run mode",
      "Review differential pressure sensor across bypass filter",
      "Verify gear oil sump temperature remains between 50 °C and 70 °C",
      "Prepare replacement filter cartridge for scheduled morning service",
    ],
  },
  pitch_system: {
    title: "Axis Capacitor Bank Test & Low-Wind Battery Cycle",
    rationale:
      "Pitch motor drive current asymmetry or battery charge cycle warning detected. Pre-emptively testing backup capacitors prevents an emergency feathering failure.",
    steps: [
      "Inquire pitch PLC error buffer for specific axis (1, 2, or 3)",
      "Schedule emergency battery discharge test during upcoming low-wind lull (< 4 m/s)",
      "Check pitch lubrication pump cycle telemetry",
    ],
  },
  converter_grid: {
    title: "Converter Thermal De-rate & Reactive Power Setpoint (Q=0)",
    rationale:
      "Grid voltage or frequency fluctuation coupled with converter IGBT temperature rise. Setting reactive power to unity power factor (Q=0) minimizes inverter bridge switching losses.",
    steps: [
      "Adjust inverter reactive power setpoint to Q = 0 kvar (cos φ = 1.0)",
      "Inspect converter cabinet ambient and liquid cooling loop delta-T",
      "Cross-reference DNO grid substation event log for regional voltage sags",
    ],
  },
  yaw_cable: {
    title: "Execute Planned Yaw Untwist Cycle",
    rationale:
      "Nacelle position cable twist counter is approaching limit switch threshold (typically 2.5 - 3.0 turns). Unwinding now during moderate wind prevents an abrupt cable-protection trip.",
    steps: [
      "Command controlled automatic cable untwist routine",
      "Verify wind vane 1 & 2 alignment calibration post-unwind",
    ],
  },
  brake_hydraulics: {
    title: "Hydraulic Pack Accumulator Pre-Charge Verification",
    rationale:
      "Hydraulic pump duty cycle expansion suggests accumulator nitrogen pre-charge loss or minor internal spool valve bypass.",
    steps: [
      "Log hydraulic power unit pump cycle frequency (cycles/hr)",
      "Inspect brake caliper pad wear feedback switch",
      "Schedule accumulator nitrogen pressure check",
    ],
  },
};

export interface ImpactInput {
  gold: string;
  pred: string;
  score: number;
  horizon_h: number;
  outcome: Outcome;
  facts?: Record<string, number | string | boolean | null | undefined>;
  channels?: Record<string, number[]>;
}

export function computeImpact(w: ImpactInput): ImpactAssessment {
  const pNow =
    typeof w.facts?.power_last1h === "number" && Number.isFinite(w.facts.power_last1h)
      ? Math.max(0, w.facts.power_last1h)
      : w.channels?.power
        ? Math.max(0, w.channels.power[w.channels.power.length - 1] ?? 0)
        : 1200; // fallback operating power

  const targetClass = w.pred !== "none" ? w.pred : w.gold !== "none" ? w.gold : "none";
  const downtimeHours =
    w.outcome.duration_h != null && w.outcome.duration_h > 0
      ? w.outcome.duration_h
      : (DEFAULT_DOWNTIME_HOURS[targetClass] ?? 1.0);

  // Lost MWh = (Operating kW * Downtime Hours) / 1000
  const isActualOrPredictedFault = targetClass !== "none" || w.gold !== "none";
  const lostMWh = isActualOrPredictedFault
    ? Math.round(((pNow * downtimeHours) / 1000) * 10) / 10
    : 0;

  const revenueAtRiskGbp = Math.round(lostMWh * WHOLESALE_GBP_PER_MWH);
  const avoidedOpexGbp = isActualOrPredictedFault ? EMERGENCY_CALLOUT_COST_GBP - PLANNED_ACTION_COST_GBP : 0;
  const totalFinancialRiskGbp = revenueAtRiskGbp + (isActualOrPredictedFault ? EMERGENCY_CALLOUT_COST_GBP : 0);

  const avgPower24h = w.channels?.power
    ? w.channels.power.reduce((a, b) => a + b, 0) / w.channels.power.length
    : pNow;
  const capacityFactorPct = Math.round((Math.max(0, avgPower24h) / RATED_POWER_KW) * 100);

  const residual =
    typeof w.facts?.residual_last3h === "number" && Number.isFinite(w.facts.residual_last3h)
      ? Math.round(w.facts.residual_last3h)
      : 0;

  const energeticAvailabilityPct = isActualOrPredictedFault
    ? Math.max(68, Math.min(99, Math.round(98 - (lostMWh / (RATED_POWER_KW * 0.024)) * 10)))
    : 99;

  let urgency: UrgencyLevel = "nominal";
  if (w.score >= 0.5 && w.horizon_h <= 3 && pNow > 50) {
    urgency = "critical";
  } else if (w.score >= 0.35 || (w.score >= 0.25 && w.horizon_h <= 3)) {
    urgency = "advisory";
  }

  const playbook = PRESCRIPTIVE_PLAYBOOK[targetClass] ?? {
    title: "Continuous SCADA Telemetry Surveillance",
    rationale: "Operating metrics are tracking expected power curve and thermal baselines. Continue normal monitoring.",
    steps: [
      "Maintain active SCADA sensor streaming (10-min telemetry)",
      "Next scheduled routine maintenance inspection: standard cycle",
    ],
  };

  const prescriptive: PrescriptiveAction = {
    title: playbook.title,
    rationale: playbook.rationale,
    recommendedSteps: playbook.steps,
    urgency,
    potentialAvoidedDowntimeH: downtimeHours,
  };

  return {
    lostMWh,
    revenueAtRiskGbp,
    avoidedOpexGbp,
    totalFinancialRiskGbp,
    energeticAvailabilityPct,
    capacityFactorPct,
    powerCurveResidualKw: residual,
    urgency,
    leadTimeHours: w.outcome.lead_time_min != null ? Math.round((w.outcome.lead_time_min / 60) * 10) / 10 : null,
    downtimeHours: Math.round(downtimeHours * 10) / 10,
    prescriptive,
  };
}

export const fmtGbp = (amount: number): string => `£${amount.toLocaleString()}`;
export const fmtMWh = (mwh: number): string => `${mwh.toFixed(1)} MWh`;
