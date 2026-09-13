"use client";

import React from "react";
import { useStream } from "../context/StreamContext";
import { PLANTS } from "../lib/mock-data";

export function Header() {
  const {
    activeView,
    selectedPlant,
    selectedTurbineId,
    turbines,
  } = useStream();

  const currentPlant = PLANTS.find((p) => p.id === selectedPlant) || PLANTS[0];
  const selectedTurbine = turbines.find((t) => t.id === selectedTurbineId);

  return (
    <header className="h-16 bg-[#0c0e14]/80 backdrop-blur-md border-b border-white/[0.05] px-8 flex items-center justify-between sticky top-0 z-20">
      {/* View Title & Breadcrumb */}
      <div className="flex items-center gap-3">
        <h2 className="text-base font-semibold text-white tracking-tight">
          {activeView === "pipeline"
            ? "TSLM Pipeline Explainer"
            : activeView === "overview"
            ? "Fleet Overview"
            : activeView === "turbine"
            ? `Turbine Diagnostics: ${selectedTurbine?.name || selectedTurbine?.id || "KM-01"}`
            : `Model Baseline & Evaluation: ${selectedTurbine?.name || "KM-01"}`}
        </h2>
        <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
          {currentPlant.name}
        </span>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-2 bg-[#151821] border border-white/[0.06] px-3 py-1.5 rounded-full text-slate-300">
          <span className="w-2 h-2 rounded-full bg-blue-400" />
          <span className="text-xs font-medium">Dataset snapshot</span>
        </div>
      </div>
    </header>
  );
}
