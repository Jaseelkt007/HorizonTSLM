"use client";

import React from "react";
import { TurbineInfo } from "../lib/types";
import { Zap, Thermometer, Activity, ArrowDownRight, ArrowUpRight } from "lucide-react";

interface TurbineKPIsProps {
  turbine: TurbineInfo;
}

export function TurbineKPIs({ turbine }: TurbineKPIsProps) {
  const isDerated = turbine.activePower < turbine.expectedPower - 100;
  const isBearingHot = turbine.bearingTemp > 75;
  const isVibrationHigh = turbine.vibrationIndex > 0.3;

  const powerDelta = turbine.activePower - turbine.expectedPower;
  const powerDeltaPct = ((powerDelta / (turbine.expectedPower || 1)) * 100).toFixed(1);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {/* Metric 1: Current Output kW */}
      <div className="minimal-card p-5 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400">
            Active Power Output
          </span>
          <div className="text-2xl font-bold text-white mt-1 tracking-tight">
            {turbine.activePower.toLocaleString("en-GB")} <span className="text-xs font-normal text-slate-400">kW</span>
          </div>
          <div className="flex items-center gap-1.5 mt-1 text-xs">
            <span className={isDerated ? "text-rose-400 font-medium flex items-center" : "text-emerald-400 font-medium flex items-center"}>
              {isDerated ? <ArrowDownRight className="w-3.5 h-3.5 mr-0.5" /> : <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />}
              {powerDeltaPct}%
            </span>
            <span className="text-slate-400">vs {turbine.expectedPower.toLocaleString("en-GB")} kW</span>
          </div>
        </div>
        <div className="w-10 h-10 rounded-full bg-blue-600/15 flex items-center justify-center text-blue-400">
          <Zap className="w-5 h-5" />
        </div>
      </div>

      {/* Metric 2: Bearing Temp */}
      <div className="minimal-card p-5 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400">
            Main Bearing Temp
          </span>
          <div className={`text-2xl font-bold mt-1 tracking-tight ${isBearingHot ? "text-rose-400" : "text-white"}`}>
            {turbine.bearingTemp} <span className="text-xs font-normal text-slate-400">°C</span>
          </div>
          <div className="flex items-center gap-1.5 mt-1 text-xs">
            <span className={isBearingHot ? "text-rose-400 font-medium" : "text-slate-400"}>
              {isBearingHot ? "SCADA value" : "SCADA value"}
            </span>
            <span className="text-slate-400">Gearbox {turbine.gearboxTemp}°C</span>
          </div>
        </div>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isBearingHot ? "bg-rose-500/15 text-rose-400" : "bg-emerald-500/15 text-emerald-400"}`}>
          <Thermometer className="w-5 h-5" />
        </div>
      </div>

      {/* Metric 3: Bearing Vibration Index */}
      <div className="minimal-card p-5 flex items-center justify-between">
        <div>
          <span className="text-xs font-medium text-slate-400">
            Vibration Index
          </span>
          <div className={`text-2xl font-bold mt-1 tracking-tight ${isVibrationHigh ? "text-rose-400" : "text-white"}`}>
            {turbine.vibrationIndex.toFixed(3)} <span className="text-xs font-normal text-slate-400">g</span>
          </div>
          <div className="flex items-center gap-1.5 mt-1 text-xs">
            <span className="text-slate-400">Tower Acceleration X channel</span>
          </div>
        </div>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${isVibrationHigh ? "bg-rose-500/15 text-rose-400" : "bg-purple-500/15 text-purple-400"}`}>
          <Activity className="w-5 h-5" />
        </div>
      </div>
    </div>
  );
}
