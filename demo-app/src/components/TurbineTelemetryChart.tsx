"use client";

import React, { useMemo, useState } from "react";
import { TelemetryPoint, TurbineInfo } from "../lib/types";
import { generateTelemetrySeries } from "../lib/mock-data";

interface TurbineTelemetryChartProps { turbine: TurbineInfo; }
type ChannelMode = "temperature" | "power" | "vibration";
type ChartPoint = TelemetryPoint & { observedValue: number };

const CHART = { width: 1000, height: 300, left: 58, right: 18, top: 18, bottom: 42 };

function formatValue(value: number, mode: ChannelMode) {
  return mode === "power"
    ? `${Math.round(value)} kW`
    : `${value.toFixed(1)} ${mode === "temperature" ? "°C" : "g"}`;
}

function TelemetryPlot({ data, mode, anomaly }: { data: ChartPoint[]; mode: ChannelMode; anomaly: boolean }) {
  const { width, height, left, right, top, bottom } = CHART;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const expected = mode === "power" ? data.map((point) => point.expectedPower).filter(Number.isFinite) : [];
  const values = [...data.map((point) => point.observedValue), ...expected];
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = Math.max((rawMax - rawMin) * 0.12, mode === "power" ? 100 : 0.25);
  const min = mode === "power" ? Math.max(0, rawMin - padding) : rawMin - padding;
  const max = rawMax + padding;
  const x = (index: number) => left + (index / Math.max(1, data.length - 1)) * plotWidth;
  const y = (value: number) => top + ((max - value) / Math.max(0.001, max - min)) * plotHeight;
  const path = (series: number[]) => series.map((value, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(2)},${y(value).toFixed(2)}`).join(" ");
  const tickIndexes = [0, 24, 48, 72, 96, 120, data.length - 1].filter((index, position, all) => index < data.length && all.indexOf(index) === position);
  const yTicks = Array.from({ length: 5 }, (_, index) => min + ((max - min) * index) / 4);
  const observedStroke = anomaly ? "#f43f5e" : mode === "vibration" ? "#a855f7" : "#38bdf8";

  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full w-full overflow-visible" role="img" aria-label={`${mode} readings over the selected 24-hour SCADA window`}>
      {yTicks.map((value) => <g key={value}>
        <line x1={left} x2={width - right} y1={y(value)} y2={y(value)} stroke="rgba(255,255,255,0.07)" />
        <text x={left - 8} y={y(value) + 4} textAnchor="end" fill="#64748b" fontSize="11">{formatValue(value, mode)}</text>
      </g>)}
      {tickIndexes.map((index) => <g key={index}>
        <line x1={x(index)} x2={x(index)} y1={top} y2={height - bottom} stroke="rgba(255,255,255,0.025)" />
        <text x={x(index)} y={height - 14} textAnchor={index === 0 ? "start" : index === data.length - 1 ? "end" : "middle"} fill="#64748b" fontSize="11">{data[index].timeLabel}</text>
      </g>)}
      {mode === "power" && <path d={path(expected)} fill="none" stroke="#f59e0b" strokeWidth="2" strokeDasharray="7 6" vectorEffect="non-scaling-stroke" />}
      <path d={path(data.map((point) => point.observedValue))} fill="none" stroke={observedStroke} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {data.map((point, index) => <circle key={point.timestamp || index} cx={x(index)} cy={y(point.observedValue)} r="2.25" fill={observedStroke}><title>{`${point.timestamp}: ${formatValue(point.observedValue, mode)}`}</title></circle>)}
    </svg>
  );
}

export function TurbineTelemetryChart({ turbine }: TurbineTelemetryChartProps) {
  const [channelMode, setChannelMode] = useState<ChannelMode>("temperature");
  const data = useMemo<ChartPoint[]>(() => {
    // The interim parquet schema stores fixed 24-hour windows: 144 samples at
    // 10-minute cadence.  Do not inherit the fleet chart's 7/30-day control,
    // which has no matching turbine telemetry series in this dataset.
    const points = generateTelemetrySeries(turbine.id, "24h", turbine.farm);
    const key: keyof TelemetryPoint = channelMode === "temperature" ? "bearingTemp" : channelMode === "power" ? "activePower" : "vibrationIndex";
    return points.map((point) => ({ ...point, observedValue: Number(point[key]) })).filter((point) => Number.isFinite(point.observedValue));
  }, [channelMode, turbine.farm, turbine.id]);

  return (
    <div className="minimal-card p-6 flex flex-col h-full min-h-0 overflow-hidden">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4 shrink-0">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold text-white tracking-tight">Sensor Telemetry Bands</h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">24h Window</span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">{data.length} raw 10-minute SCADA readings from the selected parquet window</p>
        </div>
        <div className="flex shrink-0 items-center gap-1 bg-[#10131c] p-1 rounded-full border border-white/[0.06] text-xs">
          {([["temperature", "Temperature (°C)"], ["power", "Power Output (kW)"], ["vibration", "Vibration Index (g)"]] as const).map(([id, label]) => (
            <button key={id} onClick={() => setChannelMode(id)} className={`whitespace-nowrap px-3 py-1 rounded-full font-medium transition-all ${channelMode === id ? "bg-blue-600 text-white shadow-xs" : "text-slate-400 hover:text-slate-200"}`}>{label}</button>
          ))}
        </div>
      </div>
      <div className="flex-1 min-h-[220px] w-full">
        {data.length === 0 ? <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-white/[0.08] text-xs text-slate-400">No {channelMode} readings are available in this raw SCADA window.</div> : <TelemetryPlot data={data} mode={channelMode} anomaly={turbine.status !== "normal"} />}
      </div>
      <div className="shrink-0 flex items-center gap-6 mt-3 pt-3 border-t border-white/[0.04] text-xs text-slate-400">
        <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-sky-400" /><span>Observed Sensor Reading</span></div>
        {channelMode === "power" && <div className="flex items-center gap-2"><span className="w-2.5 h-2.5 rounded-full bg-amber-400" /><span>Power-curve estimate</span></div>}
      </div>
    </div>
  );
}
