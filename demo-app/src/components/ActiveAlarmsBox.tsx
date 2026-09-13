"use client";

import React from "react";
import { TurbineInfo } from "../lib/types";
import { AlertCircle, CheckCircle, ShieldCheck } from "lucide-react";

interface ActiveAlarmsBoxProps {
  turbine: TurbineInfo;
}

export function ActiveAlarmsBox({ turbine }: ActiveAlarmsBoxProps) {
  const isCritical = turbine.status === "critical";
  const isWarning = turbine.status === "warning";

  return (
    <div className="minimal-card p-6 flex flex-col justify-between">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">
            Active Alarm Status
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Diagnostic fault codes and precursor history
          </p>
        </div>

        <span
          className={`px-3 py-1 rounded-full text-xs font-medium capitalize ${
            isCritical
              ? "bg-rose-500/15 text-rose-400"
              : isWarning
              ? "bg-amber-500/15 text-amber-400"
              : "bg-emerald-500/15 text-emerald-400"
          }`}
        >
          {turbine.status}
        </span>
      </div>

      {turbine.activeFault ? (
        <div className="space-y-4">
          <div className="p-4 rounded-2xl bg-[#10131c] border border-white/[0.04] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">
                {turbine.activeFault.replaceAll("_", " ")}
              </span>
              <span className="text-xs text-slate-400">Source: saved SCADA window</span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs pt-1">
              <div>
                <span className="text-slate-400 text-[11px] block">Subsystem</span>
                <span className="text-slate-200 font-medium capitalize">
                  {turbine.faultSubsystem?.replace("_", " ") || "Drive Train"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 text-[11px] block">Source window</span>
                <span className="text-rose-400 font-medium">{(turbine as any).sourceWindowId}</span>
              </div>
              <div>
                <span className="text-slate-400 text-[11px] block">Observed Event Lead</span>
                <span className="text-amber-400 font-medium">{turbine.predictedTTF || "No observed event"}</span>
              </div>
              <div>
                <span className="text-slate-400 text-[11px] block">Confidence</span>
                <span className="text-blue-400 font-medium">{turbine.anomalyConfidence}% (OpenTSLM)</span>
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-400 flex items-center justify-between px-1">
            <span>Prediction and event labels are from the selected source window.</span>
          </div>
        </div>
      ) : (
        <div className="p-8 rounded-2xl bg-[#10131c] border border-white/[0.04] text-center space-y-2">
          <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto opacity-80" />
          <div className="text-xs font-semibold text-white">No Selected-Window Alert</div>
          <p className="text-xs text-slate-400 max-w-xs mx-auto">
            The saved model prediction for this selected SCADA window is “none”.
          </p>
        </div>
      )}
    </div>
  );
}
