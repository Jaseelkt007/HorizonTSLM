"use client";

import { useRouter } from "next/navigation";

import { cls, fmt, turbineKey } from "@/lib/format";
import type { WindowSummary } from "@/lib/types";

import styles from "./FarmBoard.module.css";

/** A turbine's sampled windows in time order: bar = P(fault stop), dot = a fault stop really followed. */
export default function HistoryStrip({ list }: { list: WindowSummary[] }) {
  const router = useRouter();
  const n = list.length;
  const W = 260, H = 36, top = 3, bh = 22, dotY = 32;
  const slot = W / n;
  const bw = Math.max(3, Math.min(10, slot - 2));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${n} sampled windows in time order`}>
      {list.map((w, i) => {
        const x = i * slot + (slot - bw) / 2;
        const h = Math.max(2, Math.round(w.score * bh));
        const title = `${w.anchor} · asked ${w.horizon_h} h ahead · P(fault stop) ${fmt(w.score, 2)} · ${
          w.gold === "none" ? "no fault stop followed" : `${cls(w.gold)} stop followed`
        }`;
        return (
          <g key={w.id}>
            <rect
              className={styles.bar}
              x={x.toFixed(1)}
              y={top + bh - h}
              width={bw.toFixed(1)}
              height={h}
              rx={1}
              fill={w.score >= 0.5 ? "var(--risk)" : "var(--risk-track)"}
              onClick={(e) => {
                e.stopPropagation();
                router.push(`/window/${w.id}/?turbine=${encodeURIComponent(turbineKey(w))}`);
              }}
            >
              <title>{title}</title>
            </rect>
            {w.gold !== "none" && <circle cx={(x + bw / 2).toFixed(1)} cy={dotY} r={2.4} fill="var(--ink)" />}
          </g>
        );
      })}
    </svg>
  );
}
