"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { cls, tname } from "@/lib/format";
import { computeImpact, fmtGbp, fmtMWh } from "@/lib/impact";
import { FARM } from "@/lib/labels";
import type { UrgencyLevel, WindowSummary } from "@/lib/types";

import { IconArrow } from "./Icons";
import styles from "./OperatorTriageQueue.module.css";

interface Props {
  windows: WindowSummary[];
  limit?: number;
}

export default function OperatorTriageQueue({ windows, limit = 8 }: Props) {
  const [filterUrgency, setFilterUrgency] = useState<string>("all");
  const [filterFarm, setFilterFarm] = useState<string>("all");

  const enriched = useMemo(() => {
    return windows
      .map((w) => {
        const impact = computeImpact(w);
        return {
          w,
          impact,
        };
      })
      .sort((a, b) => {
        // Sort: critical first, then advisory, then nominal; then by financial risk desc
        const rank = (u: UrgencyLevel) => (u === "critical" ? 3 : u === "advisory" ? 2 : 1);
        const uDiff = rank(b.impact.urgency) - rank(a.impact.urgency);
        if (uDiff !== 0) return uDiff;
        return b.impact.totalFinancialRiskGbp - a.impact.totalFinancialRiskGbp;
      });
  }, [windows]);

  const filtered = useMemo(() => {
    return enriched.filter(({ w, impact }) => {
      if (filterUrgency !== "all" && impact.urgency !== filterUrgency) return false;
      if (filterFarm !== "all" && w.farm !== filterFarm) return false;
      return true;
    });
  }, [enriched, filterUrgency, filterFarm]);

  const criticalCount = enriched.filter((e) => e.impact.urgency === "critical").length;
  const advisoryCount = enriched.filter((e) => e.impact.urgency === "advisory").length;

  const displayList = limit ? filtered.slice(0, limit) : filtered;

  return (
    <div className={`card ${styles.container}`} style={{ padding: "18px 20px" }}>
      <div className={styles.header}>
        <div>
          <h2>
            <span className={styles.pulseDot} style={{ color: criticalCount > 0 ? "#ef4444" : "#10b981" }} />
            Control Room Early-Warning Dispatch Queue
          </h2>
          <span className="hint">
            Prioritized by operational urgency, energetic impact (MWh at risk), and dispatch lead time.
          </span>
        </div>
        <div className={styles.filters}>
          <div className="seg" role="group" aria-label="Urgency Filter">
            <button
              type="button"
              aria-pressed={filterUrgency === "all"}
              onClick={() => setFilterUrgency("all")}
            >
              All ({windows.length})
            </button>
            <button
              type="button"
              aria-pressed={filterUrgency === "critical"}
              onClick={() => setFilterUrgency("critical")}
              style={filterUrgency === "critical" ? { color: "#dc2626" } : undefined}
            >
              Critical ({criticalCount})
            </button>
            <button
              type="button"
              aria-pressed={filterUrgency === "advisory"}
              onClick={() => setFilterUrgency("advisory")}
              style={filterUrgency === "advisory" ? { color: "#d97706" } : undefined}
            >
              Advisory ({advisoryCount})
            </button>
          </div>
          <select
            value={filterFarm}
            onChange={(e) => setFilterFarm(e.target.value)}
            style={{
              padding: "5px 10px",
              borderRadius: "6px",
              border: "1px solid var(--line)",
              background: "var(--card-bg)",
              fontSize: "12px",
            }}
          >
            <option value="all">Both Farms</option>
            <option value="kelmarsh">Kelmarsh (Unseen Site)</option>
            <option value="penmanshiel">Penmanshiel</option>
          </select>
        </div>
      </div>

      <div className={styles.list}>
        {displayList.length === 0 ? (
          <div style={{ padding: "24px", textAlign: "center", color: "var(--ink-3)", fontSize: "13px" }}>
            No alerts matching current filter criteria. Fleet operating nominal.
          </div>
        ) : (
          displayList.map(({ w, impact }) => {
            const urgencyClass =
              impact.urgency === "critical"
                ? styles.itemCritical
                : impact.urgency === "advisory"
                  ? styles.itemAdvisory
                  : styles.itemNominal;

            const badgeClass =
              impact.urgency === "critical"
                ? styles.criticalBadge
                : impact.urgency === "advisory"
                  ? styles.advisoryBadge
                  : styles.nominalBadge;

            const targetClass = w.pred !== "none" ? w.pred : "none";

            return (
              <Link
                key={w.id}
                href={`/turbines/${w.farm}/${w.turbine}/`}
                className={`${styles.item} ${urgencyClass}`}
              >
                <div className={styles.turbineCol}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span className={styles.turbineName}>{tname(w)}</span>
                    <span className={`chip ${badgeClass}`}>{impact.urgency}</span>
                  </div>
                  <span className={styles.metaSub}>
                    {FARM[w.farm].tag} · lead window {w.horizon_h}h · {w.anchor}
                  </span>
                </div>

                <div className={styles.infoCol}>
                  <span className={styles.actionTitle}>
                    {targetClass !== "none" ? (
                      <>
                        <b>{cls(targetClass)}</b> — {impact.prescriptive.title}
                      </>
                    ) : (
                      "Nominal Operation — Normal SCADA Telemetry Envelopes"
                    )}
                  </span>
                  <span className={styles.rationale} title={impact.prescriptive.rationale}>
                    {impact.prescriptive.rationale}
                  </span>
                </div>

                <div className={styles.impactCol}>
                  <span className={`${styles.mwhValue} num`}>
                    {impact.lostMWh > 0 ? fmtMWh(impact.lostMWh) : "0.0 MWh"}
                  </span>
                  <span className={`${styles.gbpValue} num`}>
                    {impact.totalFinancialRiskGbp > 0 ? `${fmtGbp(impact.totalFinancialRiskGbp)} at risk` : "nominal"}
                  </span>
                </div>

                <div className={styles.leadCol}>
                  {w.pred !== "none" || w.score >= 0.5 ? (
                    <>
                      <span className={`${styles.leadTime} num`}>+{w.horizon_h}h</span>
                      <span className={styles.metaSub}>risk horizon</span>
                    </>
                  ) : (
                    <>
                      <span className={styles.leadNone}>clear</span>
                      <span className={styles.metaSub}>nominal</span>
                    </>
                  )}
                </div>

                <span className={styles.openBtn}>
                  Diagnose <IconArrow />
                </span>
              </Link>
            );
          })
        )}
      </div>

      {limit && filtered.length > limit && (
        <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 4 }}>
          <Link href="/windows/" className="btn sm">
            View all {filtered.length} alert windows <IconArrow />
          </Link>
        </div>
      )}
    </div>
  );
}
