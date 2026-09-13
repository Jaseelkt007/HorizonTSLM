"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { computeImpact, fmtGbp, fmtMWh } from "@/lib/impact";
import { FARM, FARMS } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import AlarmLogTable from "./AlarmLogTable";
import FleetPerformanceCharts from "./FleetPerformanceCharts";
import { IconArrow } from "./Icons";
import PlantMap3D from "./PlantMap3D";
import UpcomingMaintenance from "./UpcomingMaintenance";
import WeatherWidget from "./WeatherWidget";

interface Props {
  windows: WindowSummary[];
}

export default function FarmOverviewClient({ windows }: Props) {
  const [selectedFarm, setSelectedFarm] = useState<Farm>("kelmarsh");

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
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* 1. Header & Farm Selector */}
      <div className="pagehead" style={{ marginBottom: 0 }}>
        <div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 10px", borderRadius: 999, background: "var(--accent-soft)", color: "var(--accent-text)", fontSize: 11, fontWeight: 700, marginBottom: 8, textTransform: "uppercase" }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
            Control Room Wind Farm Command Center
          </div>
          <h1 style={{ margin: "2px 0 6px" }}>
            {f.name} <span className="muted" style={{ fontWeight: 500 }}>· {f.type}</span>
          </h1>
          <p className="sub" style={{ margin: 0 }}>
            {selectedFarm === "kelmarsh"
              ? "Held-out unseen test site (6 turbines, Senvion MM92 - 2.05 MW). Zero model training leakage."
              : "Training & validation site (14 turbines, Senvion MM82 - 2.05 MW). 2017–2021 SCADA telemetry."}
          </p>
        </div>

        <div className="actions" style={{ alignItems: "center" }}>
          <div className="seg" role="group" aria-label="Farm Switcher">
            {FARMS.map((fm) => (
              <button
                key={fm}
                type="button"
                aria-pressed={selectedFarm === fm}
                onClick={() => setSelectedFarm(fm)}
                style={
                  selectedFarm === fm
                    ? { background: "var(--accent-soft)", borderColor: "var(--accent-line)", fontWeight: 700 }
                    : undefined
                }
              >
                {FARM[fm].name}
              </button>
            ))}
          </div>
          <Link href="/results/" className="btn sm">
            Evaluation Benchmarks <IconArrow />
          </Link>
        </div>
      </div>

      {/* 2. Fleet Health & Core Operator KPIs */}
      <div className="kpis">
        <div className="card kpi">
          <span className="l">Wind Farm Health Index</span>
          <span className="v num" style={{ color: fleetMetrics.criticalCount > 0 ? "#ef4444" : "#10b981" }}>
            {fleetMetrics.healthScore} %
          </span>
          <span className="c">
            {fleetMetrics.criticalCount > 0
              ? `${fleetMetrics.criticalCount} turbine critical alert`
              : "All units nominal"}
          </span>
        </div>

        <div className="card kpi">
          <span className="l">Fleet Active Capacity</span>
          <span className="v num">{selectedFarm === "kelmarsh" ? "12.3 MW" : "28.7 MW"}</span>
          <span className="c">{fleetMetrics.turbinesCount} turbines active</span>
        </div>

        <div className="card kpi">
          <span className="l">Projected Generation Loss</span>
          <span className="v num">{fmtMWh(fleetMetrics.totalLostMWh)}</span>
          <span className="c">Unscheduled downtime risk</span>
        </div>

        <div className="card kpi">
          <span className="l">Direct Revenue at Risk</span>
          <span className="v num" style={{ color: fleetMetrics.totalRevenueRisk > 0 ? "#dc2626" : undefined }}>
            {fmtGbp(fleetMetrics.totalRevenueRisk)}
          </span>
          <span className="c">@ £85/MWh wholesale benchmark</span>
        </div>

        <div className="card kpi">
          <span className="l">Avoided Emergency O&M</span>
          <span className="v num" style={{ color: "#059669" }}>
            {fmtGbp(fleetMetrics.totalAvoidedOpex)}
          </span>
          <span className="c">Avoided crane / mobilization cost</span>
        </div>
      </div>

      {/* 3. Interactive 3D Plant Map with Wind Vector Simulation */}
      <PlantMap3D
        farm={selectedFarm}
        windows={windows}
      />

      {/* 4. Power Output vs. Expected & Capacity Factor (over time) */}
      <FleetPerformanceCharts
        farm={selectedFarm}
        windows={windows}
      />

      {/* 5. Meteorological Conditions & Wind Forecast */}
      <WeatherWidget
        windSpeedMs={selectedFarm === "kelmarsh" ? 13.8 : 11.2}
        windDirDeg={selectedFarm === "kelmarsh" ? 235 : 220}
        ambientTempC={selectedFarm === "kelmarsh" ? 8.4 : 7.2}
      />

      {/* 6. Upcoming Maintenance & Expected Losses */}
      <UpcomingMaintenance farm={selectedFarm} />

      {/* 7. Live SCADA Alarm & Event Log */}
      <AlarmLogTable windows={farmWindows} limit={6} />
    </div>
  );
}
