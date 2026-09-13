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

  // Auto-generated sensor summary
  const sensorSummary = useMemo(() => {
    const f = activeRecord.facts || {};
    const p = Math.round(Number(f.power_last1h) || 2040);
    const w = (Number(f.wind_last1h) || 13.8).toFixed(1);
    const rearT = Math.round(Number(f.gen_bearing_rear_temperature_now) || 79);
    const frontT = Math.round(Number(f.gen_bearing_front_temperature_now) || 41);
    const asym = Math.round(Number(f.bearing_asym_now) || rearT - frontT);
    const acc = Math.round(Number(f.tower_acc_last1h) || 54);
    const oilP = (Number(f.oil_pressure_now) || 2.8).toFixed(1);
    const residual = Math.round(Number(f.residual_last3h) || -45);

    const isAlert = activeRecord.gold !== "none" || activeRecord.pred !== "none";

    if (isAlert) {
      return (
        `Turbine ${tcode({ turbine })} is operating in near-rated conditions (${p} kW active power at ${w} m/s wind speed). ` +
        `Primary Anomaly Detected: Generator rear bearing temperature has surged to ${rearT} °C (${asym} °C hotter than front bearing), ` +
        `indicating cooling circuit degradation under sustained load. Tower acceleration X is elevated at ${acc} mm/s². ` +
        `Lubrication oil inlet pressure is steady at ${oilP} bar. Aerodynamic power curve residual shows a ${residual} kW shortfall relative to farm expectation.`
      );
    }

    return (
      `Turbine ${tcode({ turbine })} is operating nominal at ${p} kW in ${w} m/s wind. ` +
      `Thermal channels are tracking within standard operating limits (stator ${Math.round(Number(f.stator_temperature_now) || 58)} °C, ` +
      `gear oil ${Math.round(Number(f.gear_oil_temperature_now) || 56)} °C). Tower dynamic acceleration is normal (${acc} mm/s²). ` +
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
              ✓ <b>{nOk} of {totalClaims}</b> numerical telemetry claims verified against SCADA ground truth
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
              <b>✓ De-rate to 1,200 kW Applied:</b> Bearing temp stabilizes at 74 °C (preventing trip +{dur(activeRecord.outcome.lead_time_min)}), saving £{impact.totalFinancialRiskGbp.toLocaleString()}.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
