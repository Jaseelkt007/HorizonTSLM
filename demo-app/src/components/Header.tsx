"use client";

import React, { useState, useEffect } from "react";
import { useStream } from "../context/StreamContext";
import { PLANTS } from "../lib/mock-data";
import {
  Bell,
  Clock,
  MapPin,
  CheckCircle2,
  X,
  Search,
  Sliders,
} from "lucide-react";

export function Header() {
  const {
    activeView,
    selectedPlant,
    selectedTurbineId,
    turbines,
    actionToast,
    clearActionToast,
  } = useStream();

  const [utcTime, setUtcTime] = useState<string>("");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(
        now.toISOString().replace("T", " ").substring(0, 19) + " UTC"
      );
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  const currentPlant = PLANTS.find((p) => p.id === selectedPlant) || PLANTS[0];
  const selectedTurbine = turbines.find((t) => t.id === selectedTurbineId);

  return (
    <header className="h-16 bg-[#0c0e14]/80 backdrop-blur-md border-b border-white/[0.05] px-8 flex items-center justify-between sticky top-0 z-20">
      {/* View Title & Breadcrumb */}
      <div className="flex items-center gap-3">
        <h2 className="text-base font-semibold text-white tracking-tight">
          {activeView === "overview"
            ? "Fleet Overview"
            : activeView === "turbine"
            ? `Turbine Diagnostics: ${selectedTurbine?.name || selectedTurbine?.id || "KM-01"}`
            : `Model Baseline & Evaluation: ${selectedTurbine?.name || "KM-01"}`}
        </h2>
        <span className="text-xs px-2.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
          {currentPlant.name}
        </span>
      </div>

      {/* Action Toast Notification */}
      {actionToast && (
        <div className="absolute left-1/2 -translate-x-1/2 bg-blue-600 text-white px-4 py-2 rounded-full text-xs font-medium flex items-center gap-2 shadow-lg shadow-blue-500/20 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{actionToast}</span>
          <button onClick={clearActionToast} className="text-white/80 hover:text-white ml-2">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Right Controls */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1.5 text-slate-400 hidden sm:flex">
          <Clock className="w-3.5 h-3.5 text-slate-400" />
          <span>{utcTime || "14:20:00 UTC"}</span>
        </div>

        <div className="h-4 w-[1px] bg-white/[0.08] hidden sm:block" />

        <div className="flex items-center gap-2 bg-[#151821] border border-white/[0.06] px-3 py-1.5 rounded-full text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-xs font-medium">Telemetry Online</span>
        </div>
      </div>
    </header>
  );
}
