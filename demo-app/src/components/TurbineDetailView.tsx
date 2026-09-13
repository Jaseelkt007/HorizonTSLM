"use client";

import React from "react";
import { useStream } from "../context/StreamContext";
import { PLANTS } from "../lib/mock-data";
import { TurbineVectorVisual } from "./TurbineVectorVisual";
import { ActiveAlarmsBox } from "./ActiveAlarmsBox";
import { SubsystemHealthCard } from "./SubsystemHealthCard";
import { TurbineKPIs } from "./TurbineKPIs";
import { TurbineTelemetryChart } from "./TurbineTelemetryChart";
import { ModelDiagnosticBox } from "./ModelDiagnosticBox";
import { ChevronDown } from "lucide-react";

export function TurbineDetailView() {
  const {
    turbines,
    selectedTurbine,
    selectedTurbineId,
    setSelectedTurbineId,
    selectedPlant,
    setSelectedPlant,
    timeframe,
    setTimeframe,
  } = useStream();

  return (
    <div className="space-y-6 p-8 max-w-[1500px] mx-auto">
      {/* Top Controls: Plant Selector + Turbine Pills (T-01 to T-08) */}
      <div className="minimal-card p-4 flex flex-wrap items-center justify-between gap-4">
        {/* Plant Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Facility:</span>
          <div className="relative">
            <select
              value={selectedPlant}
              onChange={(e) => setSelectedPlant(e.target.value)}
              aria-label="Select Farm Facility"
              className="bg-[#10131c] border border-white/[0.06] text-white text-xs rounded-xl px-3 py-1.5 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/40 appearance-none cursor-pointer pr-8"
            >
              {PLANTS.map((plant) => (
                <option key={plant.id} value={plant.id} className="bg-[#10131c] text-white">
                  {plant.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Turbine Selector Pills (T-01 to T-08) */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1">
          <span className="text-xs text-slate-400 font-medium mr-2 hidden sm:inline">
            Units:
          </span>
          {turbines.map((t) => {
            const isSelected = t.id === selectedTurbineId;
            const isCritical = t.status === "critical";
            const isWarning = t.status === "warning";

            return (
              <button
                key={t.id}
                onClick={() => setSelectedTurbineId(t.id)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-2 ${
                  isSelected
                    ? "bg-white text-slate-950 font-semibold shadow-sm"
                    : "bg-white/[0.04] text-slate-300 hover:text-white hover:bg-white/[0.08]"
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full ${
                    isCritical
                      ? "bg-rose-500"
                      : isWarning
                      ? "bg-amber-400"
                      : "bg-emerald-400"
                  }`}
                />
                <span>{t.name}</span>
              </button>
            );
          })}
        </div>

        {/* Timeframe Selector Pills */}
        <div className="flex items-center gap-1 bg-[#10131c] p-1 rounded-xl border border-white/[0.06]">
          {(["24h"] as const).map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                timeframe === tf
                  ? "bg-white text-slate-900 font-semibold shadow-xs"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              24h
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Left = Visual & Thermal Breakdown, Right = KPIs, Telemetry & Assistant */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <TurbineVectorVisual turbine={selectedTurbine} />
          <SubsystemHealthCard turbine={selectedTurbine} />
          <ActiveAlarmsBox turbine={selectedTurbine} />
        </div>

        {/* Right Column (7 cols) */}
        <div className="lg:col-span-7 space-y-6">
          <TurbineKPIs turbine={selectedTurbine} />
          <TurbineTelemetryChart turbine={selectedTurbine} />
          <ModelDiagnosticBox turbine={selectedTurbine} />
        </div>
      </div>
    </div>
  );
}
