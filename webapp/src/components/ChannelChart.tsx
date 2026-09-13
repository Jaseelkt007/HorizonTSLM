"use client";

import { useRef, useState } from "react";

import { dur } from "@/lib/format";
import { CHANNEL_SHORT } from "@/lib/labels";
import type { ChannelMeta } from "@/lib/types";

import styles from "./Chart.module.css";

const W = 250, H = 100, PL = 36, PR = 8, PT = 8, PB = 18;

const tick = (t: number) => (Math.abs(t) >= 100 ? t.toFixed(0) : Math.abs(t) >= 10 ? t.toFixed(1) : t.toFixed(2));

/** One channel over 24 h: last hour shaded, an emphasised endpoint, crosshair + tooltip on hover/touch. */
export default function ChannelChart({ meta, values, cited }: { meta: ChannelMeta; values: number[]; cited: boolean }) {
  const [hover, setHover] = useState<{ i: number; left: number; top: number } | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const figRef = useRef<HTMLElement>(null);
  const n = values.length;
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 1e-6) { hi = lo + 1; lo -= 1; }
  const pad = (hi - lo) * 0.1;
  lo -= pad; hi += pad;
  const X = (i: number) => PL + (i / (n - 1)) * (W - PL - PR);
  const Y = (v: number) => PT + (1 - (v - lo) / (hi - lo)) * (H - PT - PB);
  const d = values.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const ticks = [lo + pad, hi - pad];
  const color = cited ? "var(--accent)" : "var(--series)";

  const show = (clientX: number) => {
    const svg = svgRef.current, fig = figRef.current;
    if (!svg || !fig) return;
    const r = svg.getBoundingClientRect(), fr = fig.getBoundingClientRect();
    const fx = ((clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(((fx - PL) / (W - PL - PR)) * (n - 1))));
    // tooltip is positioned inside the figure
    setHover({ i, left: (X(i) / W) * r.width + (r.left - fr.left), top: (Y(values[i]) / H) * r.height + (r.top - fr.top) });
  };
  const hide = () => setHover(null);
  const minutesAgo = hover ? (n - 1 - hover.i) * 10 : 0;

  return (
    <figure ref={figRef} className={`${styles.fig} ${cited ? styles.cited : ""}`}>
      <figcaption className={styles.cap}>
        <span className={styles.name} title={meta.label}>{CHANNEL_SHORT[meta.name] ?? meta.label}</span>
        <span className={styles.unit}>{tick(values[n - 1])} {meta.unit}</span>
      </figcaption>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${meta.label} over 24 hours, last value ${tick(values[n - 1])} ${meta.unit}`}
        onMouseMove={(e) => show(e.clientX)}
        onMouseLeave={hide}
        onTouchStart={(e) => show(e.touches[0].clientX)}
        onTouchMove={(e) => show(e.touches[0].clientX)}
        onTouchEnd={hide}
      >
        <rect x={X(n - 7).toFixed(1)} y={PT} width={(X(n - 1) - X(n - 7)).toFixed(1)} height={H - PT - PB} fill="var(--band)" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PL} x2={W - PR} y1={Y(t).toFixed(1)} y2={Y(t).toFixed(1)} stroke="var(--line)" strokeWidth={1} />
            <text x={PL - 5} y={(Y(t) + 3.5).toFixed(1)} textAnchor="end" fontSize={10} fill="var(--ink-3)">{tick(t)}</text>
          </g>
        ))}
        {[0, 6, 12, 18, 24].map((h) => (
          <text key={h} x={X(h * 6).toFixed(1)} y={H - 5} textAnchor={h === 0 ? "start" : h === 24 ? "end" : "middle"} fontSize={10} fill="var(--ink-3)">
            {h === 24 ? "now" : `−${24 - h} h`}
          </text>
        ))}
        <path d={d} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={X(n - 1).toFixed(1)} cy={Y(values[n - 1]).toFixed(1)} r={3} fill={color} stroke="var(--surface)" strokeWidth={1.5} />
        {hover && <line x1={X(hover.i).toFixed(1)} x2={X(hover.i).toFixed(1)} y1={PT} y2={H - PB} stroke="var(--ink-3)" strokeWidth={1} />}
        <rect x={PL} y={0} width={W - PL - PR} height={H} fill="transparent" />
      </svg>
      {hover && (
        <div className={styles.tip} style={{ left: hover.left, top: hover.top }}>
          {minutesAgo ? `−${dur(minutesAgo)}` : "now"} · {tick(values[hover.i])} {meta.unit}
        </div>
      )}
    </figure>
  );
}
