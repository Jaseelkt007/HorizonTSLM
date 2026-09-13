"use client";

import React from "react";
import { useStream } from "../context/StreamContext";
import { Zap, Activity, ArrowUpRight, Wind } from "lucide-react";

export function OverviewKPICards() {
  const { fleetKPIs, turbines } = useStream();

  const activeAlarms = turbines.filter((t) => t.status !== "normal");

  return (
    <div className="flex flex-col gap-4">
      {/* Card 1: Total Fleet Output (Matching "Revenue" card) */}
      <div className="minimal-card p-5 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400">
            Total Fleet Output
          </span>
          <div className="text-2xl font-bold text-white mt-1 tracking-tight">
            {fleetKPIs.totalFleetOutputMW} <span className="text-sm font-normal text-slate-400">MW</span>
          </div>
          <div className="mt-1.5 text-[11px] text-slate-400">Mean across the selected 24-hour SCADA windows</div>
        </div>

        <div className="w-10 h-10 rounded-full bg-blue-600/10 flex items-center justify-center text-blue-400">
          <Zap className="w-5 h-5" />
        </div>
      </div>

      {/* Card 2: Fleet Availability (Matching "Customers" card) */}
      <div className="minimal-card p-5 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400">
            Units represented
          </span>
          <div className="text-2xl font-bold text-white mt-1 tracking-tight">
            {turbines.length}
          </div>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/15 text-emerald-400">
              <ArrowUpRight className="w-3 h-3" />
              {turbines.length - activeAlarms.length}/{turbines.length} Nominal
            </span>
            <span className="text-[11px] text-slate-400">
              {activeAlarms.length} alerting/derated
            </span>
          </div>
        </div>

        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-600/30">
          <Activity className="w-5 h-5" />
        </div>
      </div>

      {/* Card 3: Capacity Factor (Matching "Current Month" card with dynamic mini bar chart) */}
      <div className="minimal-card p-5 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400">
            Capacity Factor
          </span>
          <div className="text-2xl font-bold text-white mt-1 tracking-tight">
            {fleetKPIs.capacityFactorPct}%
          </div>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/15 text-emerald-400">
              <ArrowUpRight className="w-3 h-3" />
              {fleetKPIs.weatherForecast.windSpeed} m/s
            </span>
            <span className="text-[11px] text-slate-400">wind velocity</span>
          </div>
        </div>

        {/* Mini vertical bars dynamically rendered from active timeframe telemetry */}
        <div className="flex items-end gap-1.5 h-8">
          {(fleetKPIs.sparklineBars || [45, 62, 58, 75, 88, 92, 70]).map((h, i) => (
            <div
              key={i}
              className={`w-1.5 rounded-full transition-all duration-300 ${
                i === (fleetKPIs.sparklineBars?.length || 7) - 1 ? "bg-blue-500" : "bg-blue-500/30"
              }`}
              style={{ height: `${Math.max(15, Math.min(100, h))}%` }}
              title={`Step ${i + 1}: ${h}%`}
            />
          ))}
        </div>
      </div>

      {/* Card 4: Active Alarms / Weather */}
      <div
        className="minimal-card p-5 flex items-center justify-between"
      >
        <div>
          <span className="text-xs font-medium text-slate-400">
            Active Alarms
          </span>
          <div className="text-2xl font-bold text-white mt-1 tracking-tight flex items-baseline gap-2">
            <span>{activeAlarms.length} Detected</span>
            <span className="text-xs font-medium text-rose-400">
              {fleetKPIs.criticalAlarmsCount} Critical
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1.5">
            <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/15 text-rose-400">
              {activeAlarms.length > 0 ? "Action Required" : "All Nominal"}
            </span>
            <span className="text-[11px] text-slate-400 truncate max-w-[130px]">
              {activeAlarms.length > 0
                ? `${activeAlarms[0].id} ${activeAlarms[0].activeFault || ""}`
                : "Normal grid tracking"}
            </span>
          </div>
        </div>

        {/* Dynamic Wind Forecast pill */}
        <div className="text-right">
          <div className="text-xs font-semibold text-slate-200">
            {fleetKPIs.weatherForecast.windDirection}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">
            Dataset window mean
          </div>
        </div>
      </div>
    </div>
  );
}
