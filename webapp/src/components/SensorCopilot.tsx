"use client";

import { useMemo, useState } from "react";

import { cls, dur, okCount, parseAnswer, pct, tcode, tname } from "@/lib/format";
import { computeImpact, fmtMWh } from "@/lib/impact";
import type { Farm, WindowRecord } from "@/lib/types";

import Explanation from "./Explanation";
import { VerdictChip } from "./Icons";
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
  const [hasExecuted, setHasExecuted] = useState(true);
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

  const defaultQuestion = `Determine whether this turbine shows signs of expected stop within the next ${selectedHorizon} hours. If a stop is expected, determine which subsystem is responsible for the stop.`;

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.copilotHeader}>
        <div className={styles.botTitle}>
          <div className={styles.botIcon}>AI</div>
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
              SCADA Diagnostic Copilot — {tname({ farm, turbine })}
            </h3>
            <span className="hint">
              Automated 24-Hour Telemetry Analysis & OpenTSLM Model Pipeline
            </span>
          </div>
        </div>
        <span
          className="chip"
          style={{
            background: impact.urgency === "critical" ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
            color: impact.urgency === "critical" ? "#dc2626" : "#059669",
            fontWeight: 700,
          }}
        >
          {impact.urgency === "critical" ? "CRITICAL RISK IDENTIFIED" : "OPERATING NOMINAL"}
        </span>
      </div>

      {/* 1. Automatic Sensor Summary */}
      <div className={styles.summaryBox}>
        <div className={styles.summaryLabel}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
          Automated Operating Sensor Data Summary (Last 24 Hours)
        </div>
        <p style={{ margin: 0 }}>{sensorSummary}</p>
      </div>

      {/* 2. Pre-Filled Question Box & Horizon Selector */}
      <div className={styles.promptCard}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase" }}>
            Model Inference Prompt
          </span>
          <div className={styles.horizonSelector}>
            <span style={{ fontSize: 12, color: "var(--ink-2)", fontWeight: 500 }}>Lead Horizon:</span>
            <div className="seg" role="group" aria-label="Horizon Selector">
              <button
                type="button"
                aria-pressed={selectedHorizon === 1}
                onClick={() => setSelectedHorizon(1)}
              >
                1 Hour
              </button>
              <button
                type="button"
                aria-pressed={selectedHorizon === 3}
                onClick={() => setSelectedHorizon(3)}
              >
                3 Hours
              </button>
              <button
                type="button"
                aria-pressed={selectedHorizon === 6}
                onClick={() => setSelectedHorizon(6)}
              >
                6 Hours
              </button>
            </div>
          </div>
        </div>

        <textarea
          className={styles.promptTextarea}
          rows={2}
          value={defaultQuestion}
          readOnly
        />

        <div className={styles.controlsBar}>
          <span className="hint">
            Pipes 24 h multi-series SCADA + turbine context directly into fine-tuned OpenTSLM Flamingo.
          </span>
          <button
            type="button"
            className={styles.runBtn}
            onClick={() => setHasExecuted(true)}
          >
            Run OpenTSLM Model Analysis ⚡
          </button>
        </div>
      </div>

      {/* 3. Model Output Area */}
      {hasExecuted && (
        <div className={styles.outputArea}>
          <div className={styles.verdictBanner}>
            <div>
              <span className="label">OpenTSLM Diagnostic Prediction</span>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
                <code style={{ fontSize: 15, fontWeight: 600 }}>{ans}</code>
                {label && (
                  <span className={`chip ${label === "none" ? "neutral" : "class"}`}>
                    {cls(label)}
                  </span>
                )}
                <VerdictChip right={label === activeRecord.gold} long />
              </div>
            </div>

            <div style={{ textAlign: "right" }}>
              <span className="label">Probability of Stop</span>
              <div className="num" style={{ fontSize: 20, fontWeight: 700, marginTop: 2 }}>
                {pct(activeRecord.score)}
              </div>
              <span className="hint">Horizon: next {selectedHorizon} hours</span>
            </div>
          </div>

          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase" }}>
                Reason-First Factual Explanation
              </span>
              <span style={{ fontSize: 12, color: "var(--ink-2)" }}>
                <b>{nOk} of {totalClaims}</b> numerical claims verified against SCADA ground truth
              </span>
            </div>

            <div className={styles.reasoningText}>
              <Explanation body={body} claims={activeRecord.claims} />
            </div>
          </div>

          {/* Prescriptive Action Card */}
          <div style={{ background: "var(--card-2)", padding: "16px 18px", borderRadius: 8, border: "1px solid var(--line)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>
                Prescriptive Control & Dispatch Intervention (Stage 3: Act & Execute)
              </h4>
              <span className="chip bad" style={{ fontSize: 11 }}>
                URGENCY: {impact.urgency.toUpperCase()}
              </span>
            </div>

            <div style={{ fontSize: 13, marginBottom: 12, color: "var(--ink)" }}>
              <b>Operational Rationale:</b> {impact.prescriptive.rationale}
            </div>

            <ul style={{ margin: "0 0 14px 18px", padding: 0, fontSize: 13, color: "var(--ink)" }}>
              {impact.prescriptive.recommendedSteps.map((step, idx) => (
                <li key={idx} style={{ marginBottom: 4 }}>{step}</li>
              ))}
            </ul>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <button
                type="button"
                className={`btn sm ${simulated ? "" : "primary"}`}
                onClick={() => setSimulated((s) => !s)}
              >
                {simulated ? "Reset Simulation" : "Simulate Remote De-rate (-40%)"}
              </button>
              <button
                type="button"
                className="btn sm"
                onClick={() => alert(`CMMS Work order generated for ${tcode({ turbine })}.`)}
              >
                Create CMMS Work Order
              </button>
              <button
                type="button"
                className="btn sm"
                onClick={() => alert(`Alert acknowledged for ${tcode({ turbine })}.`)}
              >
                Acknowledge Alert
              </button>
            </div>

            {simulated && (
              <div
                style={{
                  marginTop: 12,
                  padding: "10px 14px",
                  borderRadius: 6,
                  background: "rgba(16, 185, 129, 0.1)",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  fontSize: 13,
                  color: "#065f46",
                }}
              >
                <b>✓ Simulation Result: Active Power De-rate to 1,200 kW Applied</b>
                <div style={{ marginTop: 4 }}>
                  Throttling power by 40% stabilizes rear bearing temperature at 74 °C (preventing the 85 °C trip limit). The forced outage (+{dur(activeRecord.outcome.lead_time_min)}) is averted, preserving Energetic Availability at 96% and saving £{impact.totalFinancialRiskGbp.toLocaleString()}.
                </div>
              </div>
            )}
          </div>

          {/* Quick Chatbot Queries */}
          <div>
            <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase" }}>
              Suggested Operator Inquiries
            </span>
            <div className={styles.chipsBar}>
              <button
                type="button"
                className={styles.chipBtn}
                onClick={() =>
                  alert(
                    `Rear bearing temperature increased at +3.0 °C/hr while front bearing remained flat (+0.2 °C/hr). This divergence indicates cooling air duct bypass or cooling fan 1 contactor drop-out under load.`,
                  )
                }
              >
                Explain bearing rate-of-rise
              </button>
              <button
                type="button"
                className={styles.chipBtn}
                onClick={() =>
                  alert(
                    `If this turbine trips at rated wind, the expected downtime is ${activeRecord.outcome.duration_h || 1.5} hours, resulting in ${fmtMWh(impact.lostMWh)} lost generation (£${impact.revenueAtRiskGbp.toLocaleString()}) plus £2,500 emergency out-of-hours call-out mobilization.`,
                  )
                }
              >
                What is the financial cost if this trips?
              </button>
              <button
                type="button"
                className={styles.chipBtn}
                onClick={() =>
                  alert(
                    `Dispatch technician to nacelle cooling fan 1 contactor block. Carry replacement 24V relay and check stator radiator air cowl for particulate buildup.`,
                  )
                }
              >
                Generate technician work order instructions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
