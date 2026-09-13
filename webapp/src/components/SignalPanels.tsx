"use client";

import { useState } from "react";

import { dur } from "@/lib/format";
import { atOffset, fmtDateTime, fmtTick, fmtValue, niceTicks, parseAnchor, stepOffset, timeTicks } from "@/lib/time";
import { useWidth } from "@/lib/useWidth";

import styles from "./SignalPanels.module.css";

export interface Series {
  name: string;
  label: string;
  unit: string;
  values: number[];
  color: string;
}

interface Props {
  anchor: string;
  series: Series[];
  horizonH: number;
  /** The stop that followed (lead time from the end of the window), or null when none did. */
  event: { leadMin: number; message: string } | null;
  panelHeight?: number;
  interactive?: boolean;
  compact?: boolean;
}

const PL = 60, PR = 14, HEAD = 26, GAP = 12, AXIS = 36, TOP = 22;

/** Stacked panels on one shared time axis: 24 h of 10-min samples, then the horizon the model was asked about
 *  and where the stop actually began. Hover moves one crosshair through every panel. */
export default function SignalPanels({ anchor, series, horizonH, event, panelHeight = 150, interactive = true, compact = false }: Props) {
  const [ref, W] = useWidth<HTMLDivElement>(960);
  const [cursor, setCursor] = useState<number | null>(null);

  const a = parseAnchor(anchor);
  const n = series[0]?.values.length ?? 144;
  const tMin = stepOffset(0, n);
  const H = horizonH * 60;
  const tMax = Math.max(H, event?.leadMin ?? 0, 180) * 1.06;
  const X = (t: number) => PL + ((t - tMin) / (tMax - tMin)) * (W - PL - PR);
  const xNow = X(0);
  const panelH = compact ? Math.round(panelHeight * 0.8) : panelHeight;
  const total = TOP + series.length * (HEAD + panelH + GAP) + AXIS;
  const narrow = W < 640;
  const ticks = timeTicks(a, tMin, tMax, compact || narrow ? 6 : 3);

  const onMove = (clientX: number, el: SVGSVGElement) => {
    const r = el.getBoundingClientRect();
    const x = ((clientX - r.left) / r.width) * W;
    const t = tMin + ((x - PL) / (W - PL - PR)) * (tMax - tMin);
    if (t > 0 || t < tMin - 5) { setCursor(null); return; }
    setCursor(Math.max(0, Math.min(n - 1, Math.round((t - tMin) / 10))));
  };
  const cur = cursor;
  const curT = cur == null ? null : stepOffset(cur, n);

  return (
    <div ref={ref} className={styles.wrap}>
      <svg
        viewBox={`0 0 ${W} ${total}`}
        width={W}
        height={total}
        role="img"
        aria-label={`${series.map((s) => s.label).join(", ")} over the 24 hours ending ${anchor}`}
        className={interactive ? styles.hit : undefined}
        onMouseMove={interactive ? (e) => onMove(e.clientX, e.currentTarget) : undefined}
        onMouseLeave={interactive ? () => setCursor(null) : undefined}
        onTouchStart={interactive ? (e) => onMove(e.touches[0].clientX, e.currentTarget) : undefined}
        onTouchMove={interactive ? (e) => onMove(e.touches[0].clientX, e.currentTarget) : undefined}
        onTouchEnd={interactive ? () => setCursor(null) : undefined}
      >
        {/* top strip: cursor readout on the left, the outcome on the right */}
        {(!narrow || curT != null) && (
          <text x={PL} y={14} fontSize={12} fill="var(--ink-2)">
            {curT != null ? `${fmtDateTime(atOffset(a, curT))} · ${curT ? `−${dur(-curT)}` : "now"}` : `24 h to ${fmtDateTime(a)} · 10-minute means`}
          </text>
        )}
        {event ? (
          (!narrow || curT == null) && (
            <text x={W - PR} y={14} fontSize={12} fontWeight={600} textAnchor="end" fill="var(--crit)">
              {event.message}
            </text>
          )
        ) : (
          (!narrow || curT == null) && <text x={W - PR} y={14} fontSize={12} textAnchor="end" fill="var(--ink-3)">nominal envelope · no stop expected in next {horizonH} h</text>
        )}


        {series.map((s, k) => {
          const top = TOP + k * (HEAD + panelH + GAP);
          const y0 = top + HEAD, y1 = y0 + panelH;
          let lo = Math.min(...s.values), hi = Math.max(...s.values);
          if (hi - lo < 1e-6) { hi = lo + 1; lo -= 1; }
          const pad = (hi - lo) * 0.08;
          lo -= pad; hi += pad;
          const Y = (v: number) => y0 + (1 - (v - lo) / (hi - lo)) * panelH;
          const yTicks = niceTicks(lo, hi, compact ? 3 : 4);
          const line = s.values.map((v, i) => `${i ? "L" : "M"}${X(stepOffset(i, n)).toFixed(1)},${Y(v).toFixed(1)}`).join("");
          const area = `${line}L${xNow.toFixed(1)},${y1}L${X(tMin).toFixed(1)},${y1}Z`;
          const vi = cur ?? n - 1;
          return (
            <g key={s.name}>
              {/* header */}
              <rect x={PL} y={top + 5} width={10} height={10} rx={2} fill={s.color} />
              <text x={PL + 16} y={top + 14} fontSize={12.5} fontWeight={600} fill="var(--ink)">{s.label}</text>
              <text x={PL + 16 + s.label.length * 7.2 + 6} y={top + 14} fontSize={11.5} fill="var(--ink-3)">{s.unit}</text>
              <text x={W - PR} y={top + 14} fontSize={12.5} fontWeight={600} textAnchor="end" fill="var(--ink)" className="num">
                {fmtValue(s.values[vi])} <tspan fontWeight={400} fill="var(--ink-3)">{s.unit}</tspan>
              </text>
              {/* plot background: last hour, future */}
              <rect x={X(-60).toFixed(1)} y={y0} width={(xNow - X(-60)).toFixed(1)} height={panelH} fill="var(--band)" />
              <rect x={xNow.toFixed(1)} y={y0} width={(W - PR - xNow).toFixed(1)} height={panelH} fill="var(--future)" />
              {yTicks.map((t) => (
                <g key={t}>
                  <line x1={PL} x2={W - PR} y1={Y(t).toFixed(1)} y2={Y(t).toFixed(1)} stroke="var(--line)" strokeWidth={1} />
                  <text x={PL - 8} y={(Y(t) + 3.5).toFixed(1)} fontSize={11} textAnchor="end" fill="var(--ink-3)">{fmtTick(t)}</text>
                </g>
              ))}
              <line x1={PL} x2={W - PR} y1={y1} y2={y1} stroke="var(--line-2)" strokeWidth={1} />
              <path d={area} fill={s.color} opacity={0.08} />
              <path d={line} fill="none" stroke={s.color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
              <circle cx={xNow.toFixed(1)} cy={Y(s.values[n - 1]).toFixed(1)} r={3} fill={s.color} stroke="var(--card)" strokeWidth={1.5} />
              {/* now + event lines */}
              <line x1={xNow.toFixed(1)} x2={xNow.toFixed(1)} y1={y0} y2={y1} stroke="var(--ink-2)" strokeWidth={1} />
              {event && <line x1={X(event.leadMin).toFixed(1)} x2={X(event.leadMin).toFixed(1)} y1={y0 - 4} y2={y1} stroke="var(--crit)" strokeWidth={2} />}
              {/* crosshair */}
              {cur != null && (
                <g>
                  <line x1={X(stepOffset(cur, n)).toFixed(1)} x2={X(stepOffset(cur, n)).toFixed(1)} y1={y0} y2={y1} stroke="var(--ink-3)" strokeWidth={1} />
                  <circle cx={X(stepOffset(cur, n)).toFixed(1)} cy={Y(s.values[cur]).toFixed(1)} r={3.5} fill={s.color} stroke="var(--card)" strokeWidth={2} />
                </g>
              )}
            </g>
          );
        })}

        {/* time axis */}
        {(() => {
          const yA = TOP + series.length * (HEAD + panelH + GAP) - GAP + 4;
          return (
            <g>
              {ticks.filter((t) => Math.abs(X(t.min) - xNow) > 40 && (t.min <= 0 || W - PR - X(t.min) > 26)).map((t) => (
                <g key={t.min}>
                  <line x1={X(t.min).toFixed(1)} x2={X(t.min).toFixed(1)} y1={yA - 4} y2={yA} stroke="var(--line-2)" strokeWidth={1} />
                  <text x={X(t.min).toFixed(1)} y={yA + 13} fontSize={11} textAnchor="middle" fill="var(--ink-3)">{t.label}</text>
                  {t.day && !compact && t.min <= 0 && <text x={X(t.min).toFixed(1)} y={yA + 27} fontSize={11} textAnchor="middle" fill="var(--ink-4)">{t.day}</text>}
                </g>
              ))}
              <text x={xNow.toFixed(1)} y={yA + 13} fontSize={11} fontWeight={600} textAnchor="middle" fill="var(--ink)">now</text>
              {W - PR - xNow > 90 && (
                <text x={((xNow + W - PR) / 2).toFixed(1)} y={yA + 27} fontSize={11} textAnchor="middle" fill="var(--accent-ink)">asked: next {horizonH} h</text>
              )}
              {event && (
                <path d={`M${X(event.leadMin).toFixed(1)},${TOP + HEAD - 1} l-4,-6 h8 z`} fill="var(--crit)" />
              )}
            </g>
          );
        })()}
      </svg>
    </div>
  );
}
