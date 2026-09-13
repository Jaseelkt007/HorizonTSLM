"use client";

import React, { useMemo, useRef, useState } from "react";
import { TurbineInfo } from "../lib/types";
import { useSavedWindow, type SavedSeries } from "../lib/useSavedWindow";

interface TurbineTelemetryChartProps {
  turbine: TurbineInfo;
}

/** The channel groups of the prompt, in the order the model's channel descriptions use them. */
const GROUPS: { id: string; label: string; channels: string[] }[] = [
  { id: "temperature", label: "Temperatures", channels: ["stator_temperature", "gen_bearing_front_temperature", "gen_bearing_rear_temperature", "gear_oil_temperature", "main_bearing_temperature", "ambient_temperature"] },
  { id: "power", label: "Power & wind", channels: ["power", "power_curve_residual", "wind_speed"] },
  { id: "rotor", label: "Rotor & pitch", channels: ["rotor_speed", "pitch_angle"] },
  { id: "grid", label: "Grid", channels: ["grid_voltage", "grid_frequency", "reactive_power"] },
  { id: "structure", label: "Vibration & oil", channels: ["tower_acceleration_x", "gear_oil_inlet_pressure"] },
  { id: "yaw", label: "Yaw", channels: ["wind_direction", "nacelle_position", "yaw_misalignment"] },
];
const SHORT: Record<string, string> = {
  wind_speed: "Wind speed", wind_direction: "Wind direction", ambient_temperature: "Nacelle ambient temp.", power: "Active power",
  rotor_speed: "Rotor speed", pitch_angle: "Blade pitch angle", nacelle_position: "Nacelle position", gen_bearing_front_temperature: "Gen. bearing front",
  gen_bearing_rear_temperature: "Gen. bearing rear", stator_temperature: "Stator temperature", gear_oil_temperature: "Gear oil temperature",
  main_bearing_temperature: "Main bearing temp.", gear_oil_inlet_pressure: "Gear oil inlet pressure", reactive_power: "Reactive power",
  grid_voltage: "Grid voltage", grid_frequency: "Grid frequency", tower_acceleration_x: "Tower acceleration X", power_curve_residual: "Power-curve residual",
  yaw_misalignment: "Yaw misalignment",
};

const W = 300, H = 118, PL = 44, PR = 10, PT = 8, PB = 20, N = 144;
const fmtTick = (v: number) => (Math.abs(v) >= 1000 ? v.toLocaleString("en-GB", { maximumFractionDigits: 0 }) : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));
const fmtVal = (v: number) => (Math.abs(v) >= 1000 ? v.toLocaleString("en-GB", { maximumFractionDigits: 0 }) : Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2));
const dur = (min: number) => { const h = Math.floor(min / 60), r = min % 60; return h ? `${h} h${r ? " " + String(r).padStart(2, "0") + " min" : ""}` : `${r} min`; };

function niceTicks(lo: number, hi: number, n = 3): number[] {
  if (!(hi > lo)) return [lo];
  const raw = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(raw)), norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

/** Clock labels every 6 h for a window ending at `anchor` ("YYYY-MM-DD HH:MM"). */
function timeTicks(anchor: string): { i: number; label: string }[] {
  const m = anchor.match(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
  if (!m) return [];
  const end = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]);
  const start = end - (N - 1) * 600000;
  const out: { i: number; label: string }[] = [];
  const first = new Date(start); first.setUTCMinutes(0, 0, 0);
  while (first.getUTCHours() % 6 !== 0 || first.getTime() < start) first.setUTCHours(first.getUTCHours() + 1);
  for (let t = first.getTime(); t <= end; t += 6 * 3600000) {
    const i = (t - start) / 600000;
    if (i > N - 1 - 14) continue; // keep clear of the "now" label
    const d = new Date(t);
    out.push({ i, label: `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}` });
  }
  return out;
}

function ChannelChart({ s, anchor, cited }: { s: SavedSeries; anchor: string; cited: boolean }) {
  const [hover, setHover] = useState<number | null>(null);
  const ref = useRef<SVGSVGElement>(null);
  const y = s.values; const n = y.length;
  let lo = Math.min(...y), hi = Math.max(...y);
  if (hi - lo < 1e-6) { hi = lo + 1; lo -= 1; }
  const pad = (hi - lo) * 0.08; lo -= pad; hi += pad;
  const X = (i: number) => PL + (i / (n - 1)) * (W - PL - PR);
  const Y = (v: number) => PT + (1 - (v - lo) / (hi - lo)) * (H - PT - PB);
  const d = y.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const ticks = niceTicks(lo + pad, hi - pad, 3);
  const color = cited ? "#60a5fa" : "#94a3b8";
  const move = (clientX: number) => { const r = ref.current?.getBoundingClientRect(); if (!r) return; const fx = ((clientX - r.left) / r.width) * W; setHover(Math.max(0, Math.min(n - 1, Math.round(((fx - PL) / (W - PL - PR)) * (n - 1))))); };
  const vi = hover ?? n - 1;
  return (
    <figure className={`m-0 rounded-xl border p-2.5 pb-1.5 ${cited ? "border-blue-500/50 bg-blue-500/[0.04]" : "border-white/[0.06] bg-white/[0.02]"}`}>
      <figcaption className="mb-0.5 flex items-baseline justify-between gap-2 text-[11.5px]">
        <span className={`truncate font-semibold ${cited ? "text-blue-300" : "text-slate-200"}`} title={s.label}>{SHORT[s.name] ?? s.label}{cited ? " · cited" : ""}</span>
        <span className="whitespace-nowrap font-medium tabular-nums text-slate-400">{hover == null ? "" : `−${dur((n - 1 - vi) * 10)} · `}<span className="text-slate-100">{fmtVal(y[vi])}</span> {s.unit}</span>
      </figcaption>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full cursor-crosshair" role="img" aria-label={`${s.label} over 24 hours`}
        onMouseMove={(e) => move(e.clientX)} onMouseLeave={() => setHover(null)} onTouchStart={(e) => move(e.touches[0].clientX)} onTouchMove={(e) => move(e.touches[0].clientX)} onTouchEnd={() => setHover(null)}>
        <rect x={X(n - 7).toFixed(1)} y={PT} width={(X(n - 1) - X(n - 7)).toFixed(1)} height={H - PT - PB} fill="rgba(245,158,11,0.14)" />
        {ticks.map((t) => <g key={t}><line x1={PL} x2={W - PR} y1={Y(t).toFixed(1)} y2={Y(t).toFixed(1)} stroke="rgba(255,255,255,0.06)" /><text x={PL - 5} y={(Y(t) + 3.5).toFixed(1)} textAnchor="end" fontSize={9.5} fill="#64748b">{fmtTick(t)}</text></g>)}
        {timeTicks(anchor).map((t) => <text key={t.i} x={X(t.i).toFixed(1)} y={H - 6} fontSize={9.5} textAnchor="middle" fill="#64748b">{t.label}</text>)}
        <text x={X(n - 1).toFixed(1)} y={H - 6} fontSize={9.5} textAnchor="end" fontWeight={600} fill="#cbd5e1">now</text>
        <path d={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={X(n - 1).toFixed(1)} cy={Y(y[n - 1]).toFixed(1)} r={3} fill={color} stroke="#161c24" strokeWidth={1.5} />
        {hover != null && <g><line x1={X(hover).toFixed(1)} x2={X(hover).toFixed(1)} y1={PT} y2={H - PB} stroke="#94a3b8" strokeWidth={1} /><circle cx={X(hover).toFixed(1)} cy={Y(y[hover]).toFixed(1)} r={3.5} fill={color} stroke="#161c24" strokeWidth={2} /></g>}
      </svg>
    </figure>
  );
}

const CITES: Record<string, RegExp> = {
  wind_speed: /wind (?:rose|fell|is|was|speed|stayed|dropped|picked)|m\/s|cut-in/i, power: /producing about|power (?:rose|fell|at|is|dropped)|kW/i,
  rotor_speed: /rotor at|rotor speed|rpm/i, pitch_angle: /feather|pitch/i, power_curve_residual: /power curve|power-curve/i,
  gen_bearing_front_temperature: /front bearing|hotter than the other side/i, gen_bearing_rear_temperature: /rear bearing|hotter than the other side/i,
  stator_temperature: /stator/i, gear_oil_temperature: /gear oil temperature/i, main_bearing_temperature: /main bearing/i, ambient_temperature: /ambient/i,
  gear_oil_inlet_pressure: /oil (?:inlet )?pressure/i, tower_acceleration_x: /tower/i, grid_voltage: /grid voltage|voltage/i, grid_frequency: /grid frequency|frequency/i,
  reactive_power: /reactive/i, wind_direction: /wind direction/i, nacelle_position: /nacelle/i, yaw_misalignment: /off the wind direction|yaw|misalign/i,
};

/** The saved window's 19 SCADA channels — the exact series the model was given — as small multiples by subsystem group. */
export function TurbineTelemetryChart({ turbine }: TurbineTelemetryChartProps) {
  const saved = useSavedWindow(turbine.sourceWindowId);
  const [group, setGroup] = useState<string>("temperature");
  const cited = useMemo(() => {
    if (!saved) return new Set<string>();
    const body = saved.text.split(/Answer\s*:/i)[0];
    return new Set(Object.keys(CITES).filter((k) => CITES[k].test(body)));
  }, [saved]);
  const g = GROUPS.find((x) => x.id === group) ?? GROUPS[0];
  const series = saved ? g.channels.map((name) => saved.series.find((s) => s.name === name)).filter((s): s is SavedSeries => !!s) : [];

  return (
    <div className="minimal-card flex flex-col p-6">
      <div className="mb-4 flex shrink-0 flex-col gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-base font-bold tracking-tight text-white">Sensor Telemetry Bands</h3>
            <span className="rounded-full border border-blue-500/20 bg-blue-500/10 px-2 py-0.5 text-[10px] font-medium text-blue-400">24h Window</span>
          </div>
          <p className="mt-0.5 text-xs text-slate-400">
            {saved ? `The 24 h ending ${saved.anchor} that the model was given: ${saved.series.length} channels, 144 ten-minute means. Last hour shaded; channels the answer cites outlined.` : "The saved 24 h SCADA window behind this turbine, exactly as the model was given it."}
          </p>
        </div>
        <div className="flex w-fit max-w-full flex-wrap items-center gap-1 rounded-full border border-white/[0.06] bg-[#10131c] p-1 text-xs">
          {GROUPS.map((x) => (
            <button key={x.id} onClick={() => setGroup(x.id)} className={`whitespace-nowrap rounded-full px-3 py-1 font-medium transition-all ${group === x.id ? "bg-blue-600 text-white shadow-xs" : "text-slate-400 hover:text-slate-200"}`}>
              {x.label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-[220px]">
        {saved === undefined && <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-white/[0.08] text-xs text-slate-400">Loading the saved window…</div>}
        {saved === null && <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-white/[0.08] text-xs text-slate-400">No saved SCADA window for this turbine.</div>}
        {saved && (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {series.map((s) => <ChannelChart key={s.name} s={s} anchor={saved.anchor} cited={cited.has(s.name)} />)}
          </div>
        )}
      </div>

      <div className="mt-3 flex shrink-0 flex-wrap items-center gap-x-6 gap-y-1 border-t border-white/[0.04] pt-3 text-xs text-slate-400">
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-blue-400" /><span>Channel cited in the model&rsquo;s answer</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-full bg-slate-400" /><span>Other channel</span></div>
        <div className="flex items-center gap-2"><span className="h-2.5 w-2.5 rounded-sm bg-amber-500/40" /><span>Last hour</span></div>
        {saved && <span className="ml-auto">{turbine.sourceWindowId}</span>}
      </div>
    </div>
  );
}
