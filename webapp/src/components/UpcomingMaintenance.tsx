"use client";

import Link from "next/link";
import { useMemo } from "react";

import { cls, tcode } from "@/lib/format";
import { computeImpact, fmtGbp } from "@/lib/impact";
import type { Farm, WindowSummary } from "@/lib/types";

interface Props {
  farm: Farm;
  windows?: WindowSummary[];
}

export default function UpcomingMaintenance({ farm, windows = [] }: Props) {
  const items = useMemo(() => {
    const turbines = [...new Set(windows.map((w) => w.turbine))];
    const alerts = turbines
      .map((t) => {
        const list = windows
          .filter((w) => w.turbine === t)
          .sort((a, b) => a.anchor.localeCompare(b.anchor));
        const latest = list[list.length - 1];
        if (!latest) return null;
        const impact = computeImpact(latest);
        const hasAlert = latest.pred !== "none" || latest.score >= 0.35;
        if (!hasAlert) return null;

        return {
          id: `WO-${farm.slice(0, 3).toUpperCase()}-${String(t).padStart(2, "0")}`,
          turbine: t,
          type: impact.urgency === "critical" ? "Proactive AI Early-Warning" : "Advisory Precursor",
          subsystem: cls(latest.pred !== "none" ? latest.pred : "generator_cooling"),
          action: impact.prescriptive.title,
          scheduled: `Ahead of +${latest.horizon_h}h horizon (${latest.anchor.slice(11)})`,
          durationH: impact.downtimeHours,
          lossMWh: impact.lostMWh,
          plannedCost: 250,
          avoidedEmergencyCost: impact.avoidedOpexGbp > 0 ? 2500 : 0,
          status: impact.urgency === "critical" ? "Action Required" : "Advisory Scheduled",
        };
      })
      .filter((x): x is NonNullable<typeof x> => x !== null);

    return alerts;
  }, [windows, farm]);


  const totalLossMWh = items.reduce((acc, i) => acc + i.lossMWh, 0);
  const totalAvoided = items.reduce((acc, i) => acc + (i.avoidedEmergencyCost ? i.avoidedEmergencyCost - i.plannedCost : 0), 0);

  return (
    <div className="card" style={{ padding: "16px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Upcoming Maintenance & Loss Projections</h3>
          <span className="hint">CMMS Planned Interventions vs. Proactive AI Defect Mitigation</span>
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 12 }}>
          <span>Expected Downtime: <b>{items.reduce((a, b) => a + b.durationH, 0).toFixed(1)} h</b></span>
          <span>Projected Loss: <b>{totalLossMWh.toFixed(1)} MWh</b></span>
          <span style={{ color: "#059669", fontWeight: 600 }}>Avoided Emergency O&M: +{fmtGbp(totalAvoided)}</span>
        </div>
      </div>

      {items.length === 0 ? (
        <div style={{ padding: "28px 16px", textAlign: "center", color: "var(--ink-2)", fontSize: 13 }}>
          ✓ All {farm} turbines operating within nominal telemetry limits. No unscheduled maintenance interventions required.
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>Work Order</th>
                <th>Turbine</th>
                <th>Type</th>
                <th>Target Subsystem &amp; Action</th>
                <th>Window</th>
                <th className="r">Downtime</th>
                <th className="r">Loss (MWh)</th>
                <th className="r">O&amp;M Impact</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (

              <tr key={item.id}>
                <td className="mono" style={{ fontWeight: 600 }}>{item.id}</td>
                <td>
                  <Link href={`/turbines/${farm}/${item.turbine}`} style={{ fontWeight: 600, color: "var(--accent)" }}>
                    {tcode({ turbine: item.turbine })}
                  </Link>
                </td>
                <td>
                  <span
                    className="chip"
                    style={{
                      background: item.type.includes("Early-Warning") ? "rgba(239, 68, 68, 0.12)" : "rgba(56, 189, 248, 0.12)",
                      color: item.type.includes("Early-Warning") ? "#dc2626" : "var(--accent)",
                      fontSize: 11,
                      fontWeight: 600,
                    }}
                  >
                    {item.type}
                  </span>
                </td>
                <td>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{item.subsystem}</div>
                  <div style={{ fontSize: 12, color: "var(--ink-2)" }}>{item.action}</div>
                </td>
                <td style={{ fontSize: 12 }}>{item.scheduled}</td>
                <td className="r num">{item.durationH} h</td>
                <td className="r num">{item.lossMWh} MWh</td>
                <td className="r num" style={{ color: item.avoidedEmergencyCost > 0 ? "#059669" : undefined, fontWeight: 600 }}>
                  {item.avoidedEmergencyCost > 0 ? `+${fmtGbp(item.avoidedEmergencyCost - item.plannedCost)} saved` : fmtGbp(item.plannedCost)}
                </td>
                <td>
                  <span className={`chip ${item.status === "Action Required" ? "bad" : "neutral"}`}>
                    {item.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}

