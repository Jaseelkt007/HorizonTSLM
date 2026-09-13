"use client";

import React from "react";
import { useStream } from "../context/StreamContext";

export function AlarmTicker() {
  const { alarms } = useStream();

  return (
    <div className="minimal-card p-6 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">
            Recent Alarm Events
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Machine learning anomaly detections and early precursor alerts
          </p>
        </div>

        <span className="text-xs text-slate-400">
          Showing <strong className="text-white">{alarms.filter((a) => a.active).length}</strong> active alerts
        </span>
      </div>

      {/* Clean Table Feed */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-white/[0.06] text-slate-400 font-medium">
              <th className="py-3 px-4">Time</th>
              <th className="py-3 px-4">Turbine</th>
              <th className="py-3 px-4">Severity</th>
              <th className="py-3 px-4">Sensor Trigger</th>
              <th className="py-3 px-4">Subsystem</th>
              <th className="py-3 px-4">Predicted TTF</th>
              <th className="py-3 px-4">Confidence</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/[0.04]">
            {alarms.map((alarm) => {
              const isCritical = alarm.severity === "CRITICAL";
              const isWarning = alarm.severity === "WARNING";

              return (
                <tr
                  key={alarm.id}
                  className={`hover:bg-white/[0.02] transition-colors ${
                    !alarm.active ? "opacity-50" : ""
                  }`}
                >
                  {/* Timestamp */}
                  <td className="py-3 px-4 text-slate-400 whitespace-nowrap">
                    {alarm.timestamp}
                  </td>

                  {/* Turbine ID */}
                  <td className="py-3 px-4 font-semibold text-white whitespace-nowrap">
                    {alarm.turbineId}
                  </td>

                  {/* Severity Pill */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <span
                      className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium ${
                        isCritical
                          ? "bg-rose-500/15 text-rose-400"
                          : isWarning
                          ? "bg-amber-500/15 text-amber-400"
                          : "bg-slate-500/15 text-slate-400"
                      }`}
                    >
                      {alarm.severity}
                    </span>
                  </td>

                  {/* Sensor Trigger */}
                  <td className="py-3 px-4 text-slate-300 font-normal max-w-[240px] truncate">
                    {alarm.sensorTrigger}
                  </td>

                  {/* Subsystem */}
                  <td className="py-3 px-4 text-slate-300 whitespace-nowrap">
                    {alarm.subsystem}
                  </td>

                  {/* Predicted TTF */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <span
                      className={`font-medium ${
                        isCritical ? "text-rose-400" : isWarning ? "text-amber-400" : "text-slate-400"
                      }`}
                    >
                      {alarm.predictedTTF}
                    </span>
                  </td>

                  {/* Confidence */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <div className="w-14 bg-white/[0.08] rounded-full h-1.5 overflow-hidden">
                        <div
                          className="h-full bg-blue-500 rounded-full"
                          style={{ width: `${alarm.confidence}%` }}
                        />
                      </div>
                      <span className="text-slate-400 text-[11px]">{alarm.confidence}%</span>
                    </div>
                  </td>

                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
