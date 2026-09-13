"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { cls, tcode } from "@/lib/format";
import { computeImpact, fmtGbp } from "@/lib/impact";
import { FARM } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import styles from "./FleetMap.module.css";

interface Props {
  windows: WindowSummary[];
  defaultFarm?: Farm;
}

// Normalized coordinate layout for visualization
const LAYOUTS: Record<Farm, Record<number, { x: number; y: number }>> = {
  kelmarsh: {
    1: { x: 18, y: 32 },
    2: { x: 42, y: 24 },
    3: { x: 68, y: 30 },
    4: { x: 28, y: 72 },
    5: { x: 55, y: 76 },
    6: { x: 82, y: 68 },
  },
  penmanshiel: {
    1: { x: 14, y: 22 },
    2: { x: 32, y: 20 },
    4: { x: 52, y: 24 },
    5: { x: 72, y: 22 },
    6: { x: 88, y: 28 },
    7: { x: 20, y: 52 },
    8: { x: 40, y: 48 },
    9: { x: 60, y: 54 },
    10: { x: 80, y: 50 },
    11: { x: 16, y: 82 },
    12: { x: 36, y: 78 },
    13: { x: 56, y: 80 },
    14: { x: 74, y: 76 },
    15: { x: 90, y: 82 },
  },
};

export default function FleetMap({ windows, defaultFarm = "kelmarsh" }: Props) {
  const [farm, setFarm] = useState<Farm>(defaultFarm);

  const farmWindows = useMemo(() => windows.filter((w) => w.farm === farm), [windows, farm]);

  const turbineStates = useMemo(() => {
    const turbines = [...new Set(farmWindows.map((w) => w.turbine))].sort((a, b) => a - b);
    return turbines.map((t) => {
      const list = farmWindows
        .filter((w) => w.turbine === t)
        .sort((a, b) => a.anchor.localeCompare(b.anchor));
      const latest = list[list.length - 1];
      const impact = computeImpact(latest);
      return {
        turbine: t,
        latest,
        impact,
        hasFaultUpcoming: latest.pred !== "none" || latest.score >= 0.5,
      };
    });
  }, [farmWindows]);

  const layout = LAYOUTS[farm];

  return (
    <div className={`card ${styles.container}`} style={{ padding: "18px 20px" }}>
      <div className={styles.header}>
        <div>
          <h3 style={{ fontSize: 16, margin: 0 }}>
            Fleet Spatial Layout & Wake Topology — {FARM[farm].name}
          </h3>
          <span className="hint">
            {FARM[farm].type} · {turbineStates.length} turbines · click a turbine node to open its SCADA diagnostics
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className={styles.windIndicator}>
            <span className={styles.compassArrow} style={{ transform: "rotate(235deg)" }}>
              ⬆
            </span>
            <span>Wind: 235° SW (12.4 m/s)</span>
          </div>
          <div className="seg" role="group" aria-label="Farm Switcher">
            <button
              type="button"
              aria-pressed={farm === "kelmarsh"}
              onClick={() => setFarm("kelmarsh")}
            >
              Kelmarsh
            </button>
            <button
              type="button"
              aria-pressed={farm === "penmanshiel"}
              onClick={() => setFarm("penmanshiel")}
            >
              Penmanshiel
            </button>
          </div>
        </div>
      </div>

      <div className={styles.mapCanvas}>
        <svg className={styles.wakeGrid} width="100%" height="100%">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>

        {turbineStates.map(({ turbine, latest, impact }) => {
          const pos = layout[turbine] ?? { x: 50, y: 50 };
          const nodeStyle =
            impact.urgency === "critical"
              ? styles.nodeCritical
              : impact.urgency === "advisory"
                ? styles.nodeAdvisory
                : styles.nodeNominal;

          const dotColor =
            impact.urgency === "critical"
              ? "#ef4444"
              : impact.urgency === "advisory"
                ? "#f59e0b"
                : "#10b981";

          const subClass = latest.pred !== "none" ? latest.pred : "none";

          return (
            <Link
              key={turbine}
              href={`/turbines/${farm}/${turbine}/`}
              className={`${styles.turbineNode} ${nodeStyle}`}
              style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
              title={`Turbine ${tcode({ turbine })}: ${impact.urgency.toUpperCase()} risk. Click to inspect.`}
            >
              <div className={styles.nodeHeader}>
                <span className={styles.nodeStatusDot} style={{ background: dotColor }} />
                <span>{tcode({ turbine })}</span>
              </div>
              <span className={styles.nodeMeta}>
                {impact.urgency === "critical"
                  ? `${fmtGbp(impact.totalFinancialRiskGbp)} risk`
                  : subClass !== "none"
                    ? cls(subClass).split(" ")[0]
                    : "Nominal"}
              </span>
            </Link>
          );
        })}
      </div>

      <div className={styles.legend}>
        <div className={styles.legendItem}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#ef4444" }} />
          <span>Critical Warning (Forced outage predicted within horizon)</span>
        </div>
        <div className={styles.legendItem}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#f59e0b" }} />
          <span>Advisory Warning (Thermal/vibration drift detected)</span>
        </div>
        <div className={styles.legendItem}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#10b981" }} />
          <span>Nominal (Clean operating envelope)</span>
        </div>
        <span className="muted" style={{ marginLeft: "auto" }}>
          Wake attenuation arrows indicate downwind fatigue loading direction
        </span>
      </div>
    </div>
  );
}
