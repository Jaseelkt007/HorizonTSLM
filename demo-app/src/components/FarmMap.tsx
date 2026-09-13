"use client";

import React, { useState } from "react";
import { useStream } from "../context/StreamContext";
import { TurbineInfo } from "../lib/types";
import { Wind, ArrowUpRight } from "lucide-react";

export function FarmMap() {
  const { turbines, navigateToTurbine, selectedTurbineId, fleetKPIs } = useStream();
  const [hoveredTurbine, setHoveredTurbine] = useState<TurbineInfo | null>(null);

  return (
    <div className="minimal-card p-6 flex flex-col h-full relative overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">
            Turbine Spatial Array
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Click any turbine node to inspect subsystem telemetry
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            Nominal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            Warning
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            Critical
          </span>
        </div>
      </div>

      {/* Minimal Canvas Map */}
      <div className="relative flex-1 min-h-[280px] w-full bg-[#10131c] rounded-2xl border border-white/[0.04] overflow-hidden">
        {/* Subtle Wind flow tag */}
        <div className="absolute top-3 left-3 z-10 bg-[#181c26]/90 backdrop-blur px-3 py-1.5 rounded-full border border-white/[0.06] text-xs flex items-center gap-2 text-slate-300">
          <Wind className="w-3.5 h-3.5 text-blue-400" />
          <span>Wind: {fleetKPIs.weatherForecast.windSpeed} m/s ({fleetKPIs.weatherForecast.windDirection})</span>
        </div>

        {/* Ambient minimal grid dots */}
        <div className="absolute inset-0 bg-grid-pattern opacity-10 pointer-events-none" />

        {/* Turbine Nodes */}
        {turbines.map((t) => {
          const isSelected = t.id === selectedTurbineId;
          const isCritical = t.status === "critical";
          const isWarning = t.status === "warning";

          return (
            <div
              key={t.id}
              style={{ left: `${t.x}%`, top: `${t.y}%` }}
              className="absolute -translate-x-1/2 -translate-y-1/2 group cursor-pointer z-20"
              onClick={() => navigateToTurbine(t.id)}
              onMouseEnter={() => setHoveredTurbine(t)}
              onMouseLeave={() => setHoveredTurbine(null)}
            >
              {/* Subtle pulse ring for faults */}
              {isCritical && (
                <span className="absolute -inset-2 rounded-full bg-rose-500/20 animate-ping pointer-events-none" />
              )}
              {isWarning && (
                <span className="absolute -inset-1.5 rounded-full bg-amber-400/20 animate-pulse pointer-events-none" />
              )}

              {/* Node Button */}
              <div
                className={`relative w-9 h-9 rounded-full bg-[#161a24] border-2 flex items-center justify-center transition-all duration-200 ${
                  isCritical
                    ? "border-rose-500 shadow-md shadow-rose-500/20"
                    : isWarning
                    ? "border-amber-400 shadow-md shadow-amber-400/20"
                    : "border-emerald-400/70 hover:border-emerald-400"
                } ${isSelected ? "ring-2 ring-blue-500 scale-110" : "hover:scale-110"}`}
              >
                <span className="text-[11px] font-semibold text-white">{t.id.replace(/^T-0?/, "")}</span>
              </div>

              {/* Unit Tag Below */}
              <div className="absolute top-10 left-1/2 -translate-x-1/2 text-center whitespace-nowrap pointer-events-none">
                <span className="px-2 py-0.5 rounded-md bg-[#181c26] border border-white/[0.06] text-[10px] font-medium text-slate-300">
                  {t.id}
                </span>
              </div>
            </div>
          );
        })}

        {/* Minimal Tooltip Card */}
        {hoveredTurbine && (
          <div
            style={{
              left: `${Math.min(75, Math.max(25, hoveredTurbine.x))}%`,
              top: `${hoveredTurbine.y > 50 ? hoveredTurbine.y - 26 : hoveredTurbine.y + 14}%`,
            }}
            className="absolute -translate-x-1/2 z-30 pointer-events-none bg-[#181c26]/95 backdrop-blur border border-white/[0.08] p-3.5 rounded-2xl shadow-xl w-60 text-xs transition-all"
          >
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/[0.06]">
              <div className="flex items-center gap-1.5 font-bold text-white">
                <span>{hoveredTurbine.id}</span>
                <span className="text-slate-400 font-normal">({hoveredTurbine.name})</span>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
                  hoveredTurbine.status === "critical"
                    ? "bg-rose-500/15 text-rose-400"
                    : hoveredTurbine.status === "warning"
                    ? "bg-amber-500/15 text-amber-400"
                    : "bg-emerald-500/15 text-emerald-400"
                }`}
              >
                {hoveredTurbine.status}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-slate-400 text-[10px] block">Output</span>
                <span className="text-white font-semibold">{hoveredTurbine.activePower} kW</span>
              </div>
              <div>
                <span className="text-slate-400 text-[10px] block">Bearing Temp</span>
                <span className={hoveredTurbine.bearingTemp > 75 ? "text-rose-400 font-bold" : "text-white"}>
                  {hoveredTurbine.bearingTemp} °C
                </span>
              </div>
            </div>

            {hoveredTurbine.activeFault && (
              <div className="mt-2.5 pt-2 border-t border-white/[0.06] text-[11px] text-rose-300 font-medium">
                {hoveredTurbine.activeFault} ({hoveredTurbine.anomalyConfidence}% confidence)
              </div>
            )}

            <div className="mt-2 text-[10px] text-blue-400 font-medium flex items-center justify-end gap-1">
              <span>View turbine</span>
              <ArrowUpRight className="w-3 h-3" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
