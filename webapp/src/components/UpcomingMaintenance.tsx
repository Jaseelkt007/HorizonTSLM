"use client";

import Link from "next/link";

import { tcode } from "@/lib/format";
import { fmtGbp } from "@/lib/impact";
import type { Farm } from "@/lib/types";

interface Props {
  farm: Farm;
}

export default function UpcomingMaintenance({ farm }: Props) {
  const items =
    farm === "kelmarsh"
      ? [
          {
            id: "WO-2026-081",
            turbine: 1,
            type: "Proactive AI Early-Warning",
            subsystem: "Generator Cooling",
            action: "Inspect generator radiator fan 1 & 2 contactors; de-rate to 1.2 MW",
            scheduled: "Upcoming low-wind window (02:00–04:00)",
            durationH: 1.5,
            lossMWh: 1.8,
            plannedCost: 250,
            avoidedEmergencyCost: 2500,
            status: "Action Required",
          },
          {
            id: "WO-2026-074",
            turbine: 2,
            type: "Scheduled Statutory",
            subsystem: "Brake & Hydraulics",
            action: "Hydraulic accumulator nitrogen pre-charge pressure test",
            scheduled: "Next Tuesday 08:00",
            durationH: 0.8,
            lossMWh: 0.9,
            plannedCost: 350,
            avoidedEmergencyCost: 0,
            status: "Scheduled",
          },
          {
            id: "WO-2026-069",
            turbine: 4,
            type: "Proactive Preventive",
            subsystem: "Gearbox Lubrication",
            action: "Bypass oil filter cartridge replacement & particle count sensor calibration",
            scheduled: "Thursday 09:00",
            durationH: 2.0,
            lossMWh: 2.4,
            plannedCost: 400,
            avoidedEmergencyCost: 2500,
            status: "Scheduled",
          },
        ]
      : [
          {
            id: "WO-2026-112",
            turbine: 7,
            type: "Proactive AI Early-Warning",
            subsystem: "Generator Cooling",
            action: "Replace fan 1 thermal overload relay; clean air intake cowl",
            scheduled: "Tomorrow morning lull (04:00–06:00)",
            durationH: 1.2,
            lossMWh: 1.4,
            plannedCost: 250,
            avoidedEmergencyCost: 2500,
            status: "Action Required",
          },
          {
            id: "WO-2026-098",
            turbine: 12,
            type: "Scheduled Statutory",
            subsystem: "Pitch System",
            action: "Annual blade root bearing lubrication & pitch motor seal check",
            scheduled: "Next Wednesday 08:00",
            durationH: 3.5,
            lossMWh: 4.2,
            plannedCost: 650,
            avoidedEmergencyCost: 0,
            status: "Scheduled",
          },
        ];

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

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>Work Order</th>
              <th>Turbine</th>
              <th>Type</th>
              <th>Target Subsystem & Action</th>
              <th>Window</th>
              <th className="r">Downtime</th>
              <th className="r">Loss (MWh)</th>
              <th className="r">O&M Impact</th>
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
    </div>
  );
}
