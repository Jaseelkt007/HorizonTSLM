"use client";

import React from "react";
import { useStream } from "../context/StreamContext";
import { PLANTS } from "../lib/mock-data";
import {
  LayoutDashboard,
  Wind,
  BarChart2,
  ChevronDown,
  HelpCircle,
  Sparkles,
} from "lucide-react";
import { ActiveView, Timeframe } from "../lib/types";

export function Sidebar() {
  const {
    activeView,
    setActiveView,
    selectedPlant,
    setSelectedPlant,
    timeframe,
    setTimeframe,
  } = useStream();

  const currentPlant = PLANTS.find((p) => p.id === selectedPlant) || PLANTS[0];

  const navItems: { id: ActiveView; label: string; icon: React.ReactNode }[] = [
    {
      id: "pipeline",
      label: "TSLM Explainer",
      icon: <Sparkles className="w-4 h-4" />,
    },
    {
      id: "overview",
      label: "Dashboard",
      icon: <LayoutDashboard className="w-4 h-4" />,
    },
    {
      id: "turbine",
      label: "Turbine Unit",
      icon: <Wind className="w-4 h-4" />,
    },
    {
      id: "baseline",
      label: "Model Baseline",
      icon: <BarChart2 className="w-4 h-4" />,
    },
  ];

  const timeframes: { id: Timeframe; label: string }[] = [
    { id: "24h", label: "24h" },
  ];

  return (
    <aside className="w-64 flex-shrink-0 bg-[#11131b] border-r border-white/[0.06] flex flex-col justify-between select-none h-screen sticky top-0 z-30 px-4 py-5">
      {/* Top Header & Logo */}
      <div className="space-y-6">
        {/* Brand */}
        <div className="flex items-center gap-3 px-2">
          <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-blue-600 to-sky-400 flex items-center justify-center text-white shadow-md shadow-blue-500/25">
            <Wind className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-base font-bold text-white tracking-tight leading-tight">
              Aeolus
            </h1>
            <p className="text-xs text-slate-400 font-normal">
              Wind Fleet AI
            </p>
          </div>
        </div>

        {/* Plant Switcher Pill */}
        <div className="px-1">
          <div className="relative">
            <select
              value={selectedPlant}
              onChange={(e) => setSelectedPlant(e.target.value)}
              aria-label="Select Farm Facility"
              className="w-full bg-[#181c26] hover:bg-[#1d222f] border border-white/[0.06] text-slate-200 text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/40 transition-all appearance-none cursor-pointer pr-8"
            >
              {PLANTS.map((plant) => (
                <option key={plant.id} value={plant.id} className="bg-[#181c26] text-slate-200">
                  {plant.name}
                </option>
              ))}
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>
        </div>

        {/* Primary Navigation Menu */}
        <div className="space-y-1.5">
          <div className="text-[11px] font-medium text-slate-400 px-3 uppercase tracking-wider mb-2">
            Menu
          </div>
          {navItems.map((item) => {
            const isActive = activeView === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveView(item.id)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all ${
                  isActive
                    ? "bg-white text-slate-900 font-semibold shadow-sm"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
                }`}
              >
                <span className={isActive ? "text-blue-600" : "text-slate-400"}>
                  {item.icon}
                </span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Bottom Section: Timeframe & SCADA Data Source */}
      <div className="pt-4 border-t border-white/[0.06] space-y-3">
        {/* Timeframe selector pill */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-slate-400 px-1">
            <span>Timeframe</span>
            <span className="text-slate-400">Telemetry</span>
          </div>
          <div
            className="grid gap-1 bg-[#181c26] p-1 rounded-xl border border-white/[0.04]"
            style={{ gridTemplateColumns: `repeat(${timeframes.length}, minmax(0, 1fr))` }}
          >
            {timeframes.map((tf) => (
              <button
                key={tf.id}
                type="button"
                onClick={() => setTimeframe(tf.id)}
                aria-pressed={timeframe === tf.id}
                className={`py-1 text-xs rounded-lg transition-all ${
                  timeframe === tf.id
                    ? "bg-white text-slate-900 font-semibold shadow-xs"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {tf.label}
              </button>
            ))}
          </div>
        </div>

        {/* Telemetry Source Badge */}
        <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-[#181c26] border border-white/[0.04] text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-400" />
            <div className="text-left leading-tight">
              <span className="text-xs text-slate-200 font-medium block">SCADA Telemetry</span>
              <span className="text-[10px] text-slate-400">10-min Synced Dataset</span>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
            Zenodo
          </span>
        </div>

        {/* Profile Card / Help */}
        <div className="flex items-center justify-between px-1 pt-1">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-amber-400 to-orange-500 flex items-center justify-center text-slate-900 font-bold text-xs">
              MK
            </div>
            <div className="text-left leading-tight">
              <div className="text-xs font-medium text-slate-200">Operator</div>
              <div className="text-[10px] text-slate-400">{currentPlant.id === "kelmarsh" ? "MM92 Grid" : "MM82 Grid"}</div>
            </div>
          </div>
          <HelpCircle className="w-4 h-4 text-slate-400 hover:text-slate-300 cursor-pointer" />
        </div>
      </div>
    </aside>
  );
}
