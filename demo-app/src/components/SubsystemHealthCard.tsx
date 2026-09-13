"use client";

import React, { useState } from "react";
import { TurbineInfo } from "../lib/types";
import { useStream } from "../context/StreamContext";
import { ArrowUpRight } from "lucide-react";

interface SubsystemHealthCardProps {
  turbine?: TurbineInfo;
}

export function SubsystemHealthCard({ turbine: propTurbine }: SubsystemHealthCardProps) {
  const { selectedTurbine } = useStream();
  const turbine = propTurbine || selectedTurbine;
  const [period, setPeriod] = useState<"Day" | "Month" | "Year">("Day");

  const bearingPct = Math.min(100, Math.max(10, Math.round((turbine.bearingTemp / 100) * 100)));
  const gearboxPct = Math.min(100, Math.max(10, Math.round((turbine.gearboxTemp / 100) * 100)));
  const generatorPct = Math.min(100, Math.max(10, Math.round((turbine.generatorTemp / 100) * 100)));

  return (
    <div className="minimal-card p-6 flex flex-col justify-between">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white tracking-tight">
              Component Thermal Loads
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Unit {turbine.id} Subsystem Temperatures
            </p>
          </div>

          {/* Segmented Button */}
          <div className="flex items-center bg-[#10131b] p-0.5 rounded-lg border border-white/[0.06] text-xs">
            {(["Day", "Month", "Year"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1 rounded-md font-medium transition-all ${
                  period === p
                    ? "bg-blue-600 text-white shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {/* Large Metric Display */}
        <div className="mb-6">
          <div className="text-xs text-slate-400 font-medium">Peak Drive-Train Temperature</div>
          <div className="text-3xl font-bold text-white tracking-tight mt-0.5">
            {turbine.bearingTemp} °C
          </div>
          <div className="flex items-center gap-1.5 mt-1 text-xs">
            <span className={turbine.sigmaDivergence > 1.5 ? "text-rose-400 font-medium flex items-center" : "text-emerald-400 font-medium flex items-center"}>
              <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
              +{turbine.sigmaDivergence}σ Divergence
            </span>
            <span className="text-slate-400">on Turbine {turbine.id}</span>
          </div>
        </div>

        {/* Progress Bars */}
        <div className="space-y-4">
          {/* Item 1: Main Bearing */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-slate-200 font-medium">Main Bearing (DE)</span>
              <span className={turbine.bearingTemp > 75 ? "text-rose-400 font-semibold" : "text-slate-300 font-semibold"}>
                {turbine.bearingTemp} °C
              </span>
            </div>
            <div className="w-full bg-[#10131b] h-2 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  turbine.bearingTemp > 75 ? "bg-rose-500" : "bg-blue-500"
                }`}
                style={{ width: `${bearingPct}%` }}
              />
            </div>
          </div>

          {/* Item 2: Gearbox Oil */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-slate-200 font-medium">Gearbox High-Speed Stage</span>
              <span className="text-slate-300 font-semibold">{turbine.gearboxTemp} °C</span>
            </div>
            <div className="w-full bg-[#10131b] h-2 rounded-full overflow-hidden">
              <div
                className="bg-amber-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${gearboxPct}%` }}
              />
            </div>
          </div>

          {/* Item 3: Generator Stator Winding */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-slate-200 font-medium">Generator Stator Winding</span>
              <span className={turbine.generatorTemp > 85 ? "text-amber-400 font-semibold" : "text-slate-300 font-semibold"}>
                {turbine.generatorTemp} °C
              </span>
            </div>
            <div className="w-full bg-[#10131b] h-2 rounded-full overflow-hidden">
              <div
                className="bg-purple-500 h-full rounded-full transition-all duration-500"
                style={{ width: `${generatorPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
