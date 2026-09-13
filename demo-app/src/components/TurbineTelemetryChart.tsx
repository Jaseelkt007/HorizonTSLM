"use client";

import React, { useState, useMemo } from "react";
import { TelemetryPoint, TurbineInfo } from "../lib/types";
import { useStream } from "../context/StreamContext";
import { generateTelemetrySeries } from "../lib/mock-data";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

interface TurbineTelemetryChartProps {
  turbine: TurbineInfo;
}

type ChannelMode = "temperature" | "power" | "vibration";

export function TurbineTelemetryChart({ turbine }: TurbineTelemetryChartProps) {
  const { timeframe } = useStream();
  const [channelMode, setChannelMode] = useState<ChannelMode>("temperature");

  // Each point is a value exported from the selected turbine's raw 10-minute
  // SCADA window. Do not fall back to fabricated series when a channel is
  // unavailable: the empty state below makes that visible to the operator.
  const data = useMemo(() => {
    const points = generateTelemetrySeries(turbine.id, timeframe, turbine.farm);
    const requiredKey: keyof TelemetryPoint =
      channelMode === "temperature"
        ? "bearingTemp"
        : channelMode === "power"
          ? "activePower"
          : "vibrationIndex";
    return points.filter((point) => Number.isFinite(point[requiredKey]));
  }, [channelMode, turbine.id, timeframe, turbine.farm]);

  const isAnomalyTurbine = turbine.status !== "normal";
  const xAxisInterval = timeframe === "7d" ? 0 : timeframe === "24h" ? 5 : 3;

  return (
    <div className="minimal-card p-6 flex flex-col h-full min-h-0 overflow-hidden">
      {/* Header with Title and Segmented Channel Pills */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4 shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-white tracking-tight">
              Sensor Telemetry Bands
            </h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {timeframe === "24h" ? "24h Window" : timeframe === "7d" ? "7-Day Run" : "30-Day History"}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Continuous 10-minute SCADA values; expected power is the dataset power-curve residual derivation
          </p>
        </div>

        {/* Channel Selector Pills */}
        <div className="flex shrink-0 items-center gap-1 bg-[#10131c] p-1 rounded-full border border-white/[0.06] text-xs">
          {[
            { id: "temperature" as const, label: "Temperature (°C)" },
            { id: "power" as const, label: "Power Output (kW)" },
            { id: "vibration" as const, label: "Vibration Index (g)" },
          ].map((ch) => (
            <button
              key={ch.id}
              onClick={() => setChannelMode(ch.id)}
              className={`whitespace-nowrap px-3 py-1 rounded-full font-medium transition-all ${
                channelMode === ch.id
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {ch.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="flex-1 min-h-[220px] w-full">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-white/[0.08] text-xs text-slate-400">
            No {channelMode} readings are available in this raw SCADA window.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%" minHeight={220}>
            <ComposedChart
              key={`${turbine.farm}-${turbine.id}-${timeframe}`}
              data={data}
              margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
            >
            <defs>
              <linearGradient id="envelopeGradientMinimal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.12} />
                <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.0} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="0" stroke="rgba(255,255,255,0.04)" vertical={false} />

            <XAxis
              dataKey="timeLabel"
              stroke="#64748b"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              interval={xAxisInterval}
              tick={{ fill: "#64748b" }}
            />

            {channelMode === "temperature" && (
              <>
                <YAxis
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  domain={["auto", "auto"]}
                  tick={{ fill: "#64748b" }}
                  unit="°C"
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const p = payload[0].payload;
                      return (
                        <div className="bg-[#181c26] border border-white/[0.08] p-3 rounded-2xl shadow-xl text-xs space-y-1.5">
                          <div className="text-slate-400 text-[11px] pb-1 border-b border-white/[0.06]">
                            Time: <span className="text-white font-medium">{label}</span>
                          </div>
                          <div className="flex justify-between gap-6">
                            <span className="text-rose-400 font-medium">Bearing Temp:</span>
                            <span className="text-white font-bold">{p.bearingTemp} °C</span>
                          </div>
                          <div className="flex justify-between gap-6">
                            <span className="text-amber-400">Gearbox Temp:</span>
                            <span className="text-slate-300">{p.gearboxTemp} °C</span>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="bearingTemp"
                  stroke={isAnomalyTurbine ? "#f43f5e" : "#38bdf8"}
                  strokeWidth={2.5}
                  dot={{ r: 2, fill: isAnomalyTurbine ? "#f43f5e" : "#38bdf8", strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                  name="Bearing Temperature"
                />
              </>
            )}

            {channelMode === "power" && (
              <>
                <YAxis
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 2200]}
                  tick={{ fill: "#64748b" }}
                  unit=" kW"
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const p = payload[0].payload;
                      return (
                        <div className="bg-[#181c26] border border-white/[0.08] p-3 rounded-2xl shadow-xl text-xs space-y-1.5">
                          <div className="text-slate-400 text-[11px] pb-1 border-b border-white/[0.06]">
                            Time: <span className="text-white font-medium">{label}</span>
                          </div>
                          <div className="flex justify-between gap-6">
                            <span className="text-blue-400 font-medium">Active Power:</span>
                            <span className="text-white font-bold">{p.activePower} kW</span>
                          </div>
                          <div className="flex justify-between gap-6">
                            <span className="text-amber-400">Expected Curve:</span>
                            <span className="text-slate-300">{p.expectedPower} kW</span>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="expectedPower"
                  stroke="#f59e0b"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                  name="Expected Curve"
                />
                <Line
                  type="monotone"
                  dataKey="activePower"
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  dot={{ r: 2, fill: "#38bdf8", strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                  name="Active Power (kW)"
                />
              </>
            )}

            {channelMode === "vibration" && (
              <>
                <YAxis
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, (dataMax: number) => Math.max(0.6, Math.ceil(dataMax * 1.2 * 10) / 10)]}
                  tick={{ fill: "#64748b" }}
                  unit=" g"
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const p = payload[0].payload;
                      return (
                        <div className="bg-[#181c26] border border-white/[0.08] p-3 rounded-2xl shadow-xl text-xs space-y-1.5">
                          <div className="text-slate-400 text-[11px] pb-1 border-b border-white/[0.06]">
                            Time: <span className="text-white font-medium">{label}</span>
                          </div>
                          <div className="flex justify-between gap-6">
                            <span className="text-purple-400 font-medium">Vibration Index:</span>
                            <span className="text-white font-bold">{p.vibrationIndex} g</span>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="vibrationIndex"
                  stroke={isAnomalyTurbine ? "#f43f5e" : "#a855f7"}
                  strokeWidth={2.5}
                  dot={{ r: 2, fill: isAnomalyTurbine ? "#f43f5e" : "#a855f7", strokeWidth: 0 }}
                  activeDot={{ r: 4 }}
                  name="Vibration (g)"
                />
              </>
            )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Clean Legend */}
      <div className="shrink-0 flex items-center gap-6 mt-3 pt-3 border-t border-white/[0.04] text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-sky-400" />
          <span>Observed Sensor Reading</span>
        </div>
        {channelMode === "power" && (
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            <span>Power-curve estimate</span>
          </div>
        )}
      </div>
    </div>
  );
}
