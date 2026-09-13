"use client";

import { useMemo, useState } from "react";

import { computeImpact, fmtGbp } from "@/lib/impact";
import { FARM, FARMS } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import AlarmLogTable from "./AlarmLogTable";
import FleetPerformanceCharts from "./FleetPerformanceCharts";
import PlantMap3D from "./PlantMap3D";
import UpcomingMaintenance from "./UpcomingMaintenance";
import WeatherWidget from "./WeatherWidget";

interface Props {
  windows: WindowSummary[];
}

export default function FarmOverviewClient({ windows }: Props) {
  const [selectedFarm, setSelectedFarm] = useState<Farm>("kelmarsh");
  const [consoleTab, setConsoleTab] = useState<"performance" | "maintenance" | "alarms">("performance");

  const farmWindows = useMemo(
    () => windows.filter((w) => w.farm === selectedFarm),
    [windows, selectedFarm],
  );

  const fleetMetrics = useMemo(() => {
    const turbines = [...new Set(farmWindows.map((w) => w.turbine))];
    const latestPerTurbine = turbines.map((t) => {
      const list = farmWindows
        .filter((w) => w.turbine === t)
        .sort((a, b) => a.anchor.localeCompare(b.anchor));
      const latest = list[list.length - 1];
      return { turbine: t, w: latest, impact: computeImpact(latest) };
    });

    const criticalCount = latestPerTurbine.filter((x) => x.impact.urgency === "critical").length;
    const advisoryCount = latestPerTurbine.filter((x) => x.impact.urgency === "advisory").length;
    const nominalCount = latestPerTurbine.filter((x) => x.impact.urgency === "nominal").length;

    const totalLostMWh = latestPerTurbine.reduce((acc, x) => acc + x.impact.lostMWh, 0);
    const totalRevenueRisk = latestPerTurbine.reduce((acc, x) => acc + x.impact.revenueAtRiskGbp, 0);
    const totalAvoidedOpex = latestPerTurbine.reduce((acc, x) => acc + x.impact.avoidedOpexGbp, 0);

    // Fleet health score (100% - penalty for critical/advisory)
    const healthScore = Math.max(65, Math.round(100 - criticalCount * 12 - advisoryCount * 4));

    return {
      turbinesCount: turbines.length,
      criticalCount,
      advisoryCount,
      nominalCount,
      totalLostMWh,
      totalRevenueRisk,
      totalAvoidedOpex,
      healthScore,
      latestPerTurbine,
    };
  }, [farmWindows]);

  const f = FARM[selectedFarm];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 1. Sleek Minimalist Header */}
      <div className="pagehead" style={{ paddingBlock: "12px 0", marginBottom: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>{f.name}</h1>
            <div className="seg" role="group" aria-label="Farm Switcher">
              {FARMS.map((fm) => (
                <button
                  key={fm}
                  type="button"
                  aria-pressed={selectedFarm === fm}
                  onClick={() => setSelectedFarm(fm)}
                >
                  {FARM[fm].name}
                </button>
              ))}
            </div>
          </div>
          <p className="sub" style={{ margin: "4px 0 0", fontSize: 13 }}>
            {selectedFarm === "kelmarsh"
              ? "Held-out unseen test site (6 turbines, Senvion MM92 - 2.05 MW) · Zero training leakage"
              : "Training & validation site (14 turbines, Senvion MM82 - 2.05 MW)"}
          </p>
        </div>

        {/* Minimalist Inline Vitals */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span
            className="chip"
            style={{
              background: fleetMetrics.criticalCount > 0 ? "rgba(239, 68, 68, 0.12)" : "rgba(16, 185, 129, 0.12)",
              color: fleetMetrics.criticalCount > 0 ? "#dc2626" : "#059669",
              fontWeight: 600,
            }}
          >
            ● {fleetMetrics.healthScore}% Health
          </span>
          <span className="chip neutral">
            ⚡ {selectedFarm === "kelmarsh" ? "8.9 / 12.3 MW" : "21.4 / 28.7 MW"} Active
          </span>
          <span className="chip neutral">
            💨 {selectedFarm === "kelmarsh" ? "9.8 m/s · 235° SW" : "11.2 m/s · 220° SW"}
          </span>
          {fleetMetrics.totalRevenueRisk > 0 && (
            <span
              className="chip"
              style={{
                background: "rgba(239, 68, 68, 0.08)",
                color: "#dc2626",
                fontWeight: 600,
              }}
            >
              ⚠️ {fmtGbp(fleetMetrics.totalRevenueRisk)} at Risk
            </span>
          )}
        </div>
      </div>

      {/* 2. Centerpiece: Interactive 3D Plant Map */}
      <PlantMap3D farm={selectedFarm} windows={windows} />

      {/* 3. Consolidated Minimalist Operations Console */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
          <div className="seg" role="group" aria-label="Operations Console Tabs">
            <button
              type="button"
              aria-pressed={consoleTab === "performance"}
              onClick={() => setConsoleTab("performance")}
            >
              Fleet Performance &amp; Grid
            </button>
            <button
              type="button"
              aria-pressed={consoleTab === "maintenance"}
              onClick={() => setConsoleTab("maintenance")}
            >
              Upcoming Maintenance {fleetMetrics.criticalCount > 0 ? `(1 Urgent)` : ""}
            </button>
            <button
              type="button"
              aria-pressed={consoleTab === "alarms"}
              onClick={() => setConsoleTab("alarms")}
            >
              SCADA Alarms &amp; Weather
            </button>
          </div>
          <span className="hint" style={{ fontSize: 12 }}>
            {consoleTab === "performance" && "Actual Power vs. Expected Aerodynamic Curve & Capacity Factor"}
            {consoleTab === "maintenance" && "CMMS Work Orders, Downtime & Avoided Mobilization Costs"}
            {consoleTab === "alarms" && "Real-Time SCADA Alarms & On-Site Meteorological Feed"}
          </span>
        </div>

        {consoleTab === "performance" && (
          <FleetPerformanceCharts farm={selectedFarm} windows={windows} />
        )}

        {consoleTab === "maintenance" && (
          <div className="card" style={{ padding: "16px 20px" }}>
            <UpcomingMaintenance farm={selectedFarm} />
          </div>
        )}

        {consoleTab === "alarms" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <WeatherWidget
              windSpeedMs={selectedFarm === "kelmarsh" ? 13.8 : 11.2}
              windDirDeg={selectedFarm === "kelmarsh" ? 235 : 220}
              ambientTempC={selectedFarm === "kelmarsh" ? 8.4 : 7.2}
            />
            <AlarmLogTable windows={farmWindows} limit={5} />
          </div>
        )}
      </div>
    </div>
  );
}
