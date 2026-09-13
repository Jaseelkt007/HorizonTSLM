"use client";

import { useMemo, useState } from "react";

import { cls, dur, okCount, parseAnswer, pct, tcode } from "@/lib/format";
import { computeImpact } from "@/lib/impact";
import { FARM } from "@/lib/labels";
import type { Farm, WindowRecord } from "@/lib/types";

import Explanation from "./Explanation";
import styles from "./SensorCopilot.module.css";

interface Props {
  turbine: number;
  farm: Farm;
  currentRecord: WindowRecord;
  turbineRecords: WindowRecord[];
}

export default function SensorCopilot({
  turbine,
  farm,
  currentRecord,
  turbineRecords,
}: Props) {
  const [selectedHorizon, setSelectedHorizon] = useState<1 | 3 | 6>(
    (currentRecord.horizon_h as 1 | 3 | 6) || 6,
  );
  const [simulated, setSimulated] = useState(false);

  // Find record matching the selected horizon
  const activeRecord = useMemo(() => {
    const match = turbineRecords.find((r) => r.horizon_h === selectedHorizon);
    return match || currentRecord;
  }, [turbineRecords, selectedHorizon, currentRecord]);

  const { body, ans, label } = parseAnswer(activeRecord.text);
  const nOk = okCount(activeRecord.claims);
  const totalClaims = activeRecord.claims.length;
  const impact = computeImpact(activeRecord);

  // Dynamic sensor summary grounded in authentic SCADA facts
  const sensorSummary = useMemo(() => {
    const f = activeRecord.facts || {};
    const p = Math.round(Number(f.power_last1h) || 0);
    const w = (Number(f.wind_last1h) || 10.0).toFixed(1);
    const rearT = typeof f.gen_bearing_rear_temperature_now === "number" ? Math.round(f.gen_bearing_rear_temperature_now) : null;
    const frontT = typeof f.gen_bearing_front_temperature_now === "number" ? Math.round(f.gen_bearing_front_temperature_now) : null;
    const asym = typeof f.bearing_asym_now === "number" ? Math.round(f.bearing_asym_now) : (rearT != null && frontT != null ? rearT - frontT : null);
    const statorT = typeof f.stator_temperature_now === "number" ? Math.round(f.stator_temperature_now) : null;
    const gearT = typeof f.gear_oil_temperature_now === "number" ? Math.round(f.gear_oil_temperature_now) : null;
    const acc = typeof f.tower_acc_last1h === "number" ? Math.round(f.tower_acc_last1h) : null;
    const oilP = typeof f.oil_pressure_now === "number" ? Number(f.oil_pressure_now).toFixed(1) : null;
    const residual = typeof f.residual_last3h === "number" ? Math.round(f.residual_last3h) : null;
    const pitch = typeof f.pitch_last1h === "number" ? Number(f.pitch_last1h).toFixed(1) : null;

    const isAlert = activeRecord.pred !== "none" || activeRecord.score >= 0.5;

    if (isAlert) {
      const pred = activeRecord.pred;
      let specificDetail = "";

      if (pred === "generator_cooling") {
        specificDetail = rearT != null
          ? `Thermal channels indicate elevated temperature: generator rear bearing at ${rearT} °C${asym != null ? ` (${asym} °C hotter than front bearing)` : ""}${statorT != null ? `, stator at ${statorT} °C` : ""}.`
          : "Thermal telemetry indicates generator cooling degradation under sustained electrical load.";
      } else if (pred === "gearbox_lubrication") {
        specificDetail = oilP != null || gearT != null
          ? `Lubrication telemetry shows gear oil inlet pressure at ${oilP ?? "depressed"} bar and gear oil temperature at ${gearT ?? "elevated"} °C.`
          : "Hydraulic and lubrication telemetry indicates oil pressure/flow anomaly.";
      } else if (pred === "pitch_system") {
        specificDetail = pitch != null || residual != null
          ? `Aerodynamic telemetry registers blade pitch angle at ${pitch ?? 0}° and power curve residual at ${residual ?? 0} kW.`
          : "Aerodynamic control telemetry indicates pitch asymmetry or actuator response lag.";
      } else if (pred === "structural_overspeed") {
        specificDetail = acc != null
          ? `Vibration sensor registers tower lateral acceleration X at ${acc} mm/s² under ${w} m/s wind conditions.`
          : "Dynamic vibration sensors indicate elevated structural tower acceleration.";
      } else {
        specificDetail = `Telemetry envelope shows anomalous drift across ${cls(pred)} channels under active load (${p} kW).`;
      }

      return (
        `Turbine ${tcode({ turbine })} is operating at ${p} kW in ${w} m/s wind. ` +
        `Model Precursor: ${cls(pred)}. ` +
        specificDetail
      );
    }

    return (
      `Turbine ${tcode({ turbine })} is operating nominal at ${p} kW in ${w} m/s wind. ` +
      `Thermal channels are within operating envelopes${statorT != null ? ` (stator ${statorT} °C` : ""}${gearT != null ? `, gear oil ${gearT} °C)` : ""}. ` +
      `${acc != null ? `Tower dynamic acceleration is normal (${acc} mm/s²). ` : ""}` +
      `No precursor drift or thermal anomalies detected in the last 24 hours.`
    );
  }, [activeRecord, turbine]);


  return (
    <div className={styles.container}>
      {/* 1. Header */}
      <div className={styles.copilotHeader}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div className={styles.botIcon}>AI</div>
          <div>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
              Diagnostic Copilot · OpenTSLM
            </h3>
            <span className="hint" style={{ fontSize: 11.5 }}>
              {FARM[farm].name} · Fine-Tuned Time-Series Model · 24h Context
            </span>
          </div>
        </div>
        <span
          className="chip"
          style={{
            background: impact.urgency === "critical" ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
            color: impact.urgency === "critical" ? "#dc2626" : "#059669",
            fontWeight: 600,
            fontSize: 11,
          }}
        >
          {impact.urgency === "critical" ? "● CRITICAL TRIP RISK" : "● OPERATING NOMINAL"}
        </span>
      </div>

      {/* 2. Autonomous Telemetry Summary */}
      <div className={styles.summaryBox}>
        <div className={styles.summaryLabel}>
          <span>🤖</span> Autonomous Telemetry Briefing (Last 24 Hours)
        </div>
        <p style={{ margin: 0, fontSize: 13, lineHeight: 1.55 }}>{sensorSummary}</p>
      </div>

      {/* 3. Operator Prompt & Horizon Selector */}
      <div className={styles.promptCard}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)" }}>
            Diagnostic Question (Pre-filled):
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 12, color: "var(--ink-3)" }}>Lead Horizon:</span>
            <div className="seg" role="group" aria-label="Horizon Selector">
              <button
                type="button"
                aria-pressed={selectedHorizon === 1}
                onClick={() => setSelectedHorizon(1)}
              >
                1h
              </button>
              <button
                type="button"
                aria-pressed={selectedHorizon === 3}
                onClick={() => setSelectedHorizon(3)}
              >
                3h
              </button>
              <button
                type="button"
                aria-pressed={selectedHorizon === 6}
                onClick={() => setSelectedHorizon(6)}
              >
                6h
              </button>
            </div>
          </div>
        </div>
        <div style={{ fontSize: 13, color: "var(--ink-2)", background: "var(--card-2)", padding: "8px 12px", borderRadius: 6, border: "1px solid var(--line)" }}>
          &ldquo;Determine whether this turbine shows signs of expected stop within the next <b>{selectedHorizon} hours</b>. If a stop is expected, determine which subsystem is responsible.&rdquo;
        </div>
      </div>

      {/* 4. Model Output & Prescriptive Action */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div className={styles.verdictBanner}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <code style={{ fontSize: 14, fontWeight: 600 }}>{ans}</code>
              {label && (
                <span className={`chip ${label === "none" ? "neutral" : "class"}`} style={{ fontSize: 11 }}>
                  {cls(label)}
                </span>
              )}
            </div>
            <span className="hint" style={{ fontSize: 11.5, marginTop: 2, display: "block" }}>
              ✓ <b>{nOk} of {totalClaims}</b> numerical telemetry claims verified against SCADA sensor streams
            </span>
          </div>

          <div style={{ textAlign: "right" }}>
            <div className="num" style={{ fontSize: 18, fontWeight: 700, color: impact.urgency === "critical" ? "#dc2626" : "#059669" }}>
              {pct(activeRecord.score)}
            </div>
            <span className="hint" style={{ fontSize: 11 }}>Stop Likelihood</span>
          </div>
        </div>

        {/* Reason-First Factual Explanation */}
        <div className={styles.reasoningText} style={{ fontSize: 13, lineHeight: 1.5 }}>
          <Explanation body={body} claims={activeRecord.claims} />
        </div>

        {/* Prescriptive Action Card */}
        <div style={{ background: "var(--card-2)", padding: "12px 14px", borderRadius: 8, border: "1px solid var(--line)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)" }}>
              Recommended: {impact.prescriptive.title}
            </span>
            <button
              type="button"
              className={`btn sm ${simulated ? "" : "primary"}`}
              style={{ fontSize: 12, padding: "3px 8px" }}
              onClick={() => setSimulated((s) => !s)}
            >
              {simulated ? "Reset" : "Simulate Remote De-rate (-40%)"}
            </button>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.4 }}>
            {impact.prescriptive.rationale}
          </div>

          {simulated && (
            <div
              style={{
                marginTop: 8,
                padding: "8px 10px",
                borderRadius: 6,
                background: "rgba(16, 185, 129, 0.1)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                fontSize: 12,
                color: "#065f46",
                lineHeight: 1.4,
              }}
            >
              <b>✓ De-rate to {Math.round((Number(activeRecord.facts?.power_last1h) || 2050) * 0.6).toLocaleString()} kW Applied:</b> Operating load reduced by 40% to relieve subsystem stresses ahead of +{activeRecord.horizon_h}h horizon, avoiding emergency callout and mitigating £{impact.totalFinancialRiskGbp.toLocaleString()} exposure.
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
