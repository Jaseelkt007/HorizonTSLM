"use client";

import React from "react";
import { useStream } from "../context/StreamContext";
import { PLANTS } from "../lib/mock-data";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Calendar, ChevronDown } from "lucide-react";

export function FleetStatusDonut() {
  const { turbines, selectedPlant, fleetKPIs } = useStream();

  const currentPlant = PLANTS.find((p) => p.id === selectedPlant) || PLANTS[0];

  const nominalCount = turbines.filter((t) => t.status === "normal").length;
  const warningCount = turbines.filter((t) => t.status === "warning").length;
  const criticalCount = turbines.filter((t) => t.status === "critical").length;

  const data = [
    { name: "Nominal", value: nominalCount, color: "#2563eb" }, // Blue
    { name: "Warning", value: warningCount, color: "#8b5cf6" }, // Purple
    { name: "Critical", value: criticalCount, color: "#f97316" }, // Coral/Amber
  ];

  return (
    <div className="minimal-card p-6 flex flex-col justify-between h-full">
      {/* Header with Date range pill (Matching "Oct - Nov 2019" in reference image) */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold text-white tracking-tight">
          Fleet Health Breakdown
        </h3>

        <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-xs text-slate-300">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <span>{currentPlant.name}</span>
          <ChevronDown className="w-3 h-3 text-slate-400" />
        </div>
      </div>

      {/* Donut Chart & Legend in side-by-side layout (Matching reference image) */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 flex-1">
        {/* Ring Chart with Centered Total */}
        <div className="relative w-44 h-44 flex items-center justify-center">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={68}
                paddingAngle={4}
                dataKey="value"
                strokeWidth={0}
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const p = payload[0];
                    return (
                      <div className="bg-[#181c26] border border-white/[0.08] px-2.5 py-1.5 rounded-lg text-xs shadow-lg text-white">
                        <span style={{ color: p.payload.color }} className="font-semibold">
                          {p.name}:
                        </span>{" "}
                        {p.value} Turbines
                      </div>
                    );
                  }
                  return null;
                }}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Centered Total Counter */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
            <span className="text-[11px] text-slate-400 font-medium">Total</span>
            <span className="text-xl font-bold text-white tracking-tight leading-none">
              {turbines.length}
            </span>
            <span className="text-[10px] text-slate-400">Turbines</span>
          </div>
        </div>

        {/* Legend list (Matching right side of donut in reference image) */}
        <div className="space-y-2.5 text-xs">
          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600" />
              <span className="text-slate-300">Nominal Operation</span>
            </div>
            <span className="font-semibold text-white">{nominalCount}</span>
          </div>

          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-500" />
              <span className="text-slate-300">Warning</span>
            </div>
            <span className="font-semibold text-white">{warningCount}</span>
          </div>

          <div className="flex items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
              <span className="text-slate-300">Critical Anomaly</span>
            </div>
            <span className="font-semibold text-rose-400">{criticalCount}</span>
          </div>

          <div className="flex items-center justify-between gap-6 pt-1.5 border-t border-white/[0.04]">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="text-slate-300">Wind Velocity</span>
            </div>
            <span className="font-semibold text-slate-200">{fleetKPIs.weatherForecast.windSpeed} m/s</span>
          </div>
        </div>
      </div>
    </div>
  );
}
