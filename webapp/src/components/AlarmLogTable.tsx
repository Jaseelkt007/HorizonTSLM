"use client";

import Link from "next/link";
import { useState } from "react";

import { cls, tname } from "@/lib/format";
import type { WindowSummary } from "@/lib/types";

import { IconArrow } from "./Icons";

interface Props {
  windows: WindowSummary[];
  limit?: number;
}

export default function AlarmLogTable({ windows, limit = 7 }: Props) {
  const [filterSeverity, setFilterSeverity] = useState<string>("all");

  const alarmRows = windows
    .filter((w) => w.pred !== "none" || w.score >= 0.35)
    .map((w) => {
      const isCritical = w.score >= 0.5;
      const severity = isCritical ? "Critical Alert" : "Advisory Warning";
      const sub = w.pred !== "none" ? w.pred : "generator_cooling";
      const code =
        sub === "generator_cooling"
          ? "2550"
          : sub === "structural_overspeed"
            ? "3120"
            : sub === "gearbox_lubrication"
              ? "1420"
              : "2100";
      return {
        w,
        severity,
        code,
        message: `SCADA Alarm Precursor: ${cls(sub)}`,
      };
    })
    .sort((a, b) => b.w.anchor.localeCompare(a.w.anchor));

  const filtered = alarmRows.filter((r) => {
    if (filterSeverity === "critical" && !r.severity.includes("Critical")) return false;
    if (filterSeverity === "advisory" && !r.severity.includes("Advisory")) return false;
    return true;
  });

  const displayed = limit ? filtered.slice(0, limit) : filtered;

  return (
    <div className="card" style={{ padding: "16px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Live SCADA Event &amp; Alarm Journal</h3>
          <span className="hint">Controller Status Logs &amp; Telemetry Early Warnings</span>
        </div>
        <div className="seg" role="group" aria-label="Severity filter">
          <button type="button" aria-pressed={filterSeverity === "all"} onClick={() => setFilterSeverity("all")}>All ({alarmRows.length})</button>
          <button type="button" aria-pressed={filterSeverity === "critical"} onClick={() => setFilterSeverity("critical")}>Critical</button>
          <button type="button" aria-pressed={filterSeverity === "advisory"} onClick={() => setFilterSeverity("advisory")}>Advisory</button>
        </div>
      </div>

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Turbine</th>
              <th>Status / Severity</th>
              <th>Fault Code</th>
              <th>Alarm Precursor Message</th>
              <th>Lead Horizon</th>
              <th className="r">Action</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map(({ w, severity, code, message }) => {
              const isCrit = severity.includes("Critical");
              return (
                <tr key={w.id}>
                  <td className="num">{w.anchor}</td>
                  <td><b>{tname(w)}</b></td>
                  <td>
                    <span
                      className="chip"
                      style={{
                        background: isCrit ? "rgba(239, 68, 68, 0.12)" : "rgba(245, 158, 11, 0.12)",
                        color: isCrit ? "#dc2626" : "#d97706",
                        fontWeight: 600,
                        fontSize: 11,
                      }}
                    >
                      {severity}
                    </span>
                  </td>
                  <td className="mono">{code}</td>
                  <td style={{ fontWeight: 500 }}>{message}</td>
                  <td className="num" style={{ color: isCrit ? "#dc2626" : "var(--ink-2)" }}>
                    +{w.horizon_h} h lead
                  </td>
                  <td className="r">
                    <Link href={`/turbines/${w.farm}/${w.turbine}`} className="btn sm">
                      Triage <IconArrow />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
