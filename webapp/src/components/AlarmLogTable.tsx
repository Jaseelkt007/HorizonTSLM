"use client";

import Link from "next/link";
import { useState } from "react";

import { cls, dur, tname } from "@/lib/format";
import type { WindowSummary } from "@/lib/types";

import { IconArrow } from "./Icons";

interface Props {
  windows: WindowSummary[];
  limit?: number;
}

export default function AlarmLogTable({ windows, limit = 7 }: Props) {
  const [filterSeverity, setFilterSeverity] = useState<string>("all");

  const alarmRows = windows
    .filter((w) => w.gold !== "none" || w.pred !== "none")
    .map((w) => {
      const isForcedStop = w.gold !== "none";
      const isCritical = w.score >= 0.5;
      const severity = isForcedStop ? "Stop (Forced)" : isCritical ? "Warning (Imminent)" : "Advisory";
      return {
        w,
        severity,
        code: w.gold === "generator_cooling" ? "2550" : w.gold === "structural_overspeed" ? "3120" : w.gold === "gearbox_lubrication" ? "1420" : "2100",
        message: w.outcome.message ?? (w.pred !== "none" ? `Precursor drift: ${cls(w.pred)}` : "Turbine Controller Status Warning"),
      };
    })
    .sort((a, b) => b.w.anchor.localeCompare(a.w.anchor));

  const filtered = alarmRows.filter((r) => {
    if (filterSeverity === "stop" && !r.severity.includes("Stop")) return false;
    if (filterSeverity === "warning" && !r.severity.includes("Warning")) return false;
    return true;
  });

  const displayed = limit ? filtered.slice(0, limit) : filtered;

  return (
    <div className="card" style={{ padding: "16px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Live SCADA Event & Alarm Journal</h3>
          <span className="hint">Controller Status Logs & TSLM Early-Warning Interceptions</span>
        </div>
        <div className="seg" role="group" aria-label="Severity filter">
          <button type="button" aria-pressed={filterSeverity === "all"} onClick={() => setFilterSeverity("all")}>All Events ({alarmRows.length})</button>
          <button type="button" aria-pressed={filterSeverity === "stop"} onClick={() => setFilterSeverity("stop")}>Forced Stops</button>
          <button type="button" aria-pressed={filterSeverity === "warning"} onClick={() => setFilterSeverity("warning")}>Early Warnings</button>
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
              <th>Message</th>
              <th>Lead Time</th>
              <th className="r">Action</th>
            </tr>
          </thead>
          <tbody>
            {displayed.map(({ w, severity, code, message }) => {
              const isStop = severity.includes("Stop");
              return (
                <tr key={w.id}>
                  <td className="num">{w.anchor}</td>
                  <td><b>{tname(w)}</b></td>
                  <td>
                    <span
                      className="chip"
                      style={{
                        background: isStop ? "rgba(239, 68, 68, 0.12)" : "rgba(245, 158, 11, 0.12)",
                        color: isStop ? "#dc2626" : "#d97706",
                        fontWeight: 600,
                        fontSize: 11,
                      }}
                    >
                      {severity}
                    </span>
                  </td>
                  <td className="mono">{code}</td>
                  <td style={{ fontWeight: 500 }}>{message}</td>
                  <td className="num" style={{ color: isStop ? "#dc2626" : "var(--ink-2)" }}>
                    {w.outcome.lead_time_min ? `+${dur(w.outcome.lead_time_min)}` : `${w.horizon_h}h window`}
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
