"use client";

import React, { useMemo, useState } from "react";
import { useStream } from "../context/StreamContext";
import { TurbineInfo } from "../lib/types";
import { ArrowUpRight, Compass, Wind } from "lucide-react";

const TILE_SIZE = 256;
// Zoom 14 shows the surveyed separation of every turbine while keeping the
// full displayed Penmanshiel array inside a standard dashboard card.
const MAP_ZOOM = 14;
const TILE_RANGE = [-2, -1, 0, 1, 2];

// Coordinates transcribed from Kelmarsh_WT_static.csv and
// Penmanshiel_WT_static.csv. Keep this lookup separate from the operational
// snapshot: telemetry refreshes must never move a physical turbine marker.
const TURBINE_COORDINATES: Record<string, Record<string, readonly [number, number]>> = {
  kelmarsh: {
    "T-01": [52.400604, -0.947133],
    "T-02": [52.402551, -0.949527],
    "T-03": [52.403834, -0.94419],
    "T-04": [52.398781, -0.94115],
    "T-05": [52.402308, -0.940537],
    "T-06": [52.400687, -0.936093],
  },
  penmanshiel: {
    "T-01": [55.902502, -2.306389],
    "T-02": [55.900008, -2.301268],
    "T-04": [55.905943, -2.30269],
    "T-05": [55.903294, -2.298367],
    "T-06": [55.900951, -2.293967],
    "T-07": [55.898741, -2.289856],
    "T-08": [55.907915, -2.297314],
    "T-09": [55.90499, -2.291806],
    "T-10": [55.903032, -2.287585],
    "T-11": [55.900852, -2.282371],
    "T-13": [55.907026, -2.285887],
    "T-14": [55.90505, -2.28165],
    "T-15": [55.902463, -2.277329],
  },
};

// Offsets are written exactly the way the browser serialises a style value (one decimal, "calc(50% - 16.2px)"
// rather than "+ -16.2px"); otherwise React sees a different string during hydration and reports a mismatch.
const offset = (v: number) => {
  const r = Math.round(v * 10) / 10;
  return `calc(50% ${r < 0 ? "-" : "+"} ${Math.abs(r)}px)`;
};

function project(lat: number, lon: number) {
  const scale = TILE_SIZE * 2 ** MAP_ZOOM;
  const safeLat = Math.max(-85.05112878, Math.min(85.05112878, lat));
  return {
    x: ((lon + 180) / 360) * scale,
    y: ((1 - Math.asinh(Math.tan((safeLat * Math.PI) / 180)) / Math.PI) / 2) * scale,
  };
}

function directionDegrees(direction: string) {
  const directions: Record<string, number> = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
  const compass = direction.toUpperCase().match(/\b(NW|NE|SW|SE|N|E|S|W)\b/)?.[1];
  return compass ? directions[compass] : 0;
}

function statusClass(status: TurbineInfo["status"]) {
  if (status === "critical") return "border-rose-500 shadow-rose-500/50";
  if (status === "warning") return "border-amber-400 shadow-amber-400/50";
  return "border-emerald-400 shadow-emerald-400/40";
}

function coordinatesFor(turbine: TurbineInfo): readonly [number, number] {
  const coordinates = TURBINE_COORDINATES[turbine.farm]?.[turbine.id];
  if (!coordinates) {
    throw new Error(`No surveyed map coordinates for ${turbine.farm}/${turbine.id}`);
  }
  return coordinates;
}

export function FarmMap() {
  const { turbines, selectedTurbineId, fleetKPIs, navigateToTurbine } = useStream();
  const [hoveredTurbine, setHoveredTurbine] = useState<TurbineInfo | null>(null);
  const mappedTurbines = useMemo(() => turbines.map((turbine) => {
    const [lat, lon] = coordinatesFor(turbine);
    return { turbine, point: project(lat, lon), lat, lon };
  }), [turbines]);
  const center = useMemo(() => project(
    mappedTurbines.reduce((sum, item) => sum + item.lat, 0) / mappedTurbines.length,
    mappedTurbines.reduce((sum, item) => sum + item.lon, 0) / mappedTurbines.length,
  ), [mappedTurbines]);
  const windDirection = fleetKPIs.weatherForecast.windDirection;
  const windDegrees = directionDegrees(windDirection);

  return (
    <div className="minimal-card p-6 flex flex-col h-full relative overflow-hidden">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">Turbine Spatial Array</h3>
          <p className="text-xs text-slate-400 mt-0.5">Live geographic layout from the selected dataset snapshot</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-400">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-400" />Nominal</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" />Warning</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-rose-500" />Critical</span>
        </div>
      </div>

      <div className="relative flex-1 min-h-[300px] w-full rounded-2xl border border-white/[0.08] overflow-hidden bg-slate-800" aria-label="Wind farm map">
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
          {TILE_RANGE.flatMap((row) => TILE_RANGE.map((column) => {
            const tileX = Math.floor(center.x / TILE_SIZE) + column;
            const tileY = Math.floor(center.y / TILE_SIZE) + row;
            return <img alt="" className="absolute max-w-none" draggable={false} height={TILE_SIZE} key={`${tileX}-${tileY}`} src={`https://tile.openstreetmap.org/${MAP_ZOOM}/${tileX}/${tileY}.png`} style={{ width: TILE_SIZE, height: TILE_SIZE, left: offset(tileX * TILE_SIZE - center.x), top: offset(tileY * TILE_SIZE - center.y) }} width={TILE_SIZE} />;
          }))}
        </div>
        <div className="absolute inset-0 pointer-events-none bg-slate-950/25" />

        <div className="absolute top-3 left-3 z-30 bg-slate-950/85 backdrop-blur px-3 py-2 rounded-xl border border-white/15 text-xs text-slate-100 shadow-lg">
          <div className="flex items-center gap-2 font-medium"><Wind className="w-4 h-4 text-sky-300" /><span>Wind {fleetKPIs.weatherForecast.windSpeed} m/s · from {windDirection}</span></div>
          <div className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-300"><span className="wind-arrow inline-flex" style={{ transform: `rotate(${windDegrees + 180}deg)` }}><Compass className="w-4 h-4 text-sky-300" /></span><span>Flowing toward {(windDegrees + 180) % 360}°</span></div>
        </div>
        <div className="absolute right-3 bottom-2 z-10 rounded bg-slate-950/75 px-1.5 py-0.5 text-[9px] text-slate-300">© OpenStreetMap contributors</div>

        {mappedTurbines.map(({ turbine, point }) => {
          const isSelected = turbine.id === selectedTurbineId;
          return (
            <div className="absolute z-20" key={turbine.id} onMouseEnter={() => setHoveredTurbine(turbine)} onMouseLeave={() => setHoveredTurbine(null)} style={{ left: offset(point.x - center.x), top: offset(point.y - center.y) }}>
              <button aria-label={`Show ${turbine.id} details`} className={`group relative -translate-x-1/2 -translate-y-1/2 h-12 w-12 rounded-full border-2 bg-slate-950/90 shadow-lg transition-transform hover:scale-110 focus:outline-none focus:ring-2 focus:ring-sky-300 ${statusClass(turbine.status)} ${isSelected ? "ring-2 ring-sky-300 ring-offset-2 ring-offset-slate-900" : ""}`} onClick={() => navigateToTurbine(turbine.id)} type="button">
                {turbine.status !== "normal" && <span className="absolute -inset-2 rounded-full border border-current opacity-60 animate-ping" />}
                <span className="turbine-rotor absolute inset-1.5 rounded-full border border-white/30" style={{ animationDuration: `${Math.max(1.4, 7 - turbine.windSpeed / 2)}s` }}><i /><i /><i /></span>
                <span className="relative text-[10px] font-bold text-white">{turbine.id.replace(/^T-0?/, "")}</span>
              </button>
              <span className="absolute left-1/2 top-7 -translate-x-1/2 rounded bg-slate-950/90 px-1.5 py-0.5 text-[9px] font-medium text-white shadow whitespace-nowrap">{turbine.id}</span>

              {hoveredTurbine?.id === turbine.id && <div className="absolute left-1/2 top-10 z-40 w-60 -translate-x-1/2 rounded-xl border border-white/15 bg-slate-950/95 p-3.5 text-xs shadow-2xl backdrop-blur" role="tooltip">
                <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2"><div className="font-bold text-white">{turbine.id} <span className="font-normal text-slate-400">({turbine.name})</span></div><span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${turbine.status === "critical" ? "bg-rose-500/15 text-rose-300" : turbine.status === "warning" ? "bg-amber-500/15 text-amber-300" : "bg-emerald-500/15 text-emerald-300"}`}>{turbine.status}</span></div>
                <div className="grid grid-cols-2 gap-2"><div><span className="block text-[10px] text-slate-400">Output</span><span className="font-semibold text-white">{turbine.activePower} kW</span></div><div><span className="block text-[10px] text-slate-400">Bearing temp</span><span className={turbine.bearingTemp > 75 ? "font-bold text-rose-300" : "text-white"}>{turbine.bearingTemp} °C</span></div></div>
                {turbine.activeFault && <div className="mt-2 border-t border-white/10 pt-2 text-[11px] font-medium text-rose-200">{turbine.activeFault} ({turbine.anomalyConfidence}% confidence)</div>}
                <button className="mt-3 ml-auto flex items-center gap-1 text-[11px] font-medium text-sky-300 hover:text-sky-200" onClick={() => navigateToTurbine(turbine.id)} type="button">View turbine <ArrowUpRight className="h-3 w-3" /></button>
              </div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
