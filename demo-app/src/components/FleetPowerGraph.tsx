"use client";

import React, { useMemo } from "react";
import { useStream } from "../context/StreamContext";
import { generateFleetPowerSeries, PLANTS } from "../lib/mock-data";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { ChevronDown } from "lucide-react";

export function FleetPowerGraph() {
  const { timeframe, setTimeframe, selectedPlant, fleetKPIs } = useStream();

  const currentPlant = PLANTS.find((p) => p.id === selectedPlant) || PLANTS[0];

  const data = useMemo(() => {
    return generateFleetPowerSeries(timeframe, selectedPlant);
  }, [timeframe, selectedPlant]);

  const latestPoint = data[data.length - 1] || data[0];

  const xAxisInterval = timeframe === "7d" ? 0 : timeframe === "24h" ? 5 : 3;

  return (
    <div className="minimal-card p-6 flex flex-col h-full">
      {/* Header with Title, Location Dropdown, and Segmented Filter Pills */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-lg font-bold text-white tracking-tight">
              Fleet Power Output
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {timeframe === "24h" ? "24h High-Res" : timeframe === "7d" ? "7-Day Run" : "30-Day Corpus"}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {timeframe === "24h"
              ? "24-hour continuous 10-min SCADA telemetry versus expected power curve"
              : timeframe === "7d"
              ? "7-day consecutive SCADA trajectory during storm event (Jan 15 – Jan 21, 2018)"
              : "30-day historical SCADA generation profile (Daily fleet aggregation)"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Location filter pill */}
          <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-xs text-slate-300">
            <span>{currentPlant.name}</span>
            <ChevronDown className="w-3 h-3 text-slate-400" />
          </div>

          {/* Timeframe Pill Selector */}
          <div className="flex items-center gap-1 bg-[#10131b] p-1 rounded-full border border-white/[0.06]">
            {[
              { id: "24h" as const, label: "24h" },
              { id: "7d" as const, label: "7 Days" },
              { id: "30d" as const, label: "30 Days" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setTimeframe(tab.id)}
                className={`px-3.5 py-1 text-xs font-medium rounded-full transition-all ${
                  timeframe === tab.id
                    ? "bg-blue-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="flex-1 w-full min-h-[260px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
            <defs>
              <linearGradient id="areaGlow" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="0" stroke="rgba(255,255,255,0.04)" vertical={false} />

            <XAxis
              dataKey="timeLabel"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              interval={xAxisInterval}
              tick={{ fill: "#64748b" }}
            />

            <YAxis
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              domain={[0, (dataMax: number) => Math.max(18, Math.ceil(dataMax * 1.15))]}
              tick={{ fill: "#64748b" }}
              unit=" MW"
            />

            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const p = payload[0].payload;
                  return (
                    <div className="bg-[#181c26] border border-white/[0.08] p-3 rounded-2xl shadow-xl text-xs space-y-1.5">
                      <div className="text-slate-400 text-[11px] pb-1 border-b border-white/[0.06]">
                        Time: <span className="text-white font-medium">{label}</span>
                      </div>
                      <div className="flex justify-between gap-6">
                        <span className="text-blue-400 font-medium">Actual Fleet Output:</span>
                        <span className="text-white font-bold">{p.actualMW} MW</span>
                      </div>
                      <div className="flex justify-between gap-6">
                        <span className="text-amber-400">Expected Curve:</span>
                        <span className="text-slate-300">{p.expectedMW} MW</span>
                      </div>
                      <div className="flex justify-between gap-6">
                        <span className="text-slate-400">Wind Speed:</span>
                        <span className="text-sky-300 font-medium">{p.windSpeed} m/s</span>
                      </div>
                      <div className="flex justify-between gap-6 pt-1 border-t border-white/[0.06]">
                        <span className="text-slate-400">Capacity Factor:</span>
                        <span className="text-emerald-400 font-semibold">{p.capacityFactor}%</span>
                      </div>
                    </div>
                  );
                }
                return null;
              }}
            />

            {/* Shaded Area */}
            <Area
              type="monotone"
              dataKey="upperMW"
              stroke="transparent"
              fill="url(#areaGlow)"
            />

            {/* Expected Power Curve */}
            <Line
              type="monotone"
              dataKey="expectedMW"
              stroke="#f59e0b"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              name="Expected Output"
            />

            {/* Actual Output Line with smooth curve and dots */}
            <Line
              type="monotone"
              dataKey="actualMW"
              stroke="#38bdf8"
              strokeWidth={2.5}
              dot={{ r: timeframe === "7d" ? 4 : 2, fill: "#38bdf8", strokeWidth: 0 }}
              activeDot={{ r: 5, fill: "#38bdf8", stroke: "#0f172a", strokeWidth: 2 }}
              name="Actual Fleet Power"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Minimal Legend below chart */}
      <div className="flex flex-wrap items-center gap-6 mt-4 pt-3 border-t border-white/[0.04] text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
          <span>Actual Power (MW)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          <span>Expected Theoretical Band</span>
        </div>
        <div className="flex items-center gap-4 ml-auto text-slate-400">
          <span>Fleet Mean: <strong className="text-slate-200">{fleetKPIs.totalFleetOutputMW} MW</strong></span>
          <span>Capacity Factor: <strong className="text-emerald-400">{fleetKPIs.capacityFactorPct}%</strong></span>
        </div>
      </div>
    </div>
  );
}
