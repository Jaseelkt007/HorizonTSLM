"use client";

import { useRouter } from "next/navigation";

import { cls, fmt } from "@/lib/format";
import type { WindowSummary } from "@/lib/types";

import styles from "./FarmView.module.css";

/** A turbine's sampled telemetry windows in time order: bar = P(trip risk). */
export default function HistoryStrip({ list }: { list: WindowSummary[] }) {
  const router = useRouter();
  const n = list.length;
  const W = 300, H = 32, top = 4, bh = 24;
  const slot = W / n;
  const bw = Math.max(3, Math.min(12, slot - 2));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${n} sampled windows in time order`}>
      <line x1={0} x2={W} y1={top + bh + 0.5} y2={top + bh + 0.5} stroke="var(--line)" />
      {list.map((w, i) => {
        const x = i * slot + (slot - bw) / 2;
        const h = Math.max(2, Math.round(w.score * bh));
        const title = `${w.anchor} · lead horizon ${w.horizon_h} h · P(fault stop) ${fmt(w.score, 2)} · ${w.pred === "none" ? "Nominal operation" : `Precursor: ${cls(w.pred)}`}`;
        return (
          <g key={w.id}>
            <rect className={styles.bar} x={x.toFixed(1)} y={top + bh - h} width={bw.toFixed(1)} height={h} rx={1} fill={w.score >= 0.5 ? "var(--risk)" : "var(--risk-track)"}
              onClick={(e) => { e.stopPropagation(); router.push(`/turbines/${w.farm}/${w.turbine}/`); }}>
              <title>{title}</title>
            </rect>
          </g>
        );
      })}
    </svg>
  );
}
