import Link from "next/link";

import FleetMap from "@/components/FleetMap";
import { cls, pct, stateLabel, tcode } from "@/lib/format";
import { computeImpact, fmtGbp, fmtMWh } from "@/lib/impact";
import { FARM } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import styles from "./FarmView.module.css";
import HistoryStrip from "./HistoryStrip";
import { IconArrow } from "./Icons";

export default function FarmView({ farm, windows }: { farm: Farm; windows: WindowSummary[] }) {
  const ws = windows.filter((w) => w.farm === farm);
  const turbines = [...new Set(ws.map((w) => w.turbine))].sort((a, b) => a - b);
  const rows = turbines
    .map((t) => {
      const list = ws.filter((w) => w.turbine === t).sort((a, b) => a.anchor.localeCompare(b.anchor));
      const latest = list[list.length - 1];
      const impact = computeImpact(latest);
      return { t, list, latest, impact };
    })
    .sort((a, b) => b.latest.score - a.latest.score || a.t - b.t);

  const alarms = ws.filter((w) => w.pred !== "none").length;
  const criticalCount = rows.filter((r) => r.impact.urgency === "critical").length;
  const advisoryCount = rows.filter((r) => r.impact.urgency === "advisory").length;
  const nominalCount = rows.filter((r) => r.impact.urgency === "nominal").length;
  const healthIndex = turbines.length > 0 ? Math.round((nominalCount / turbines.length) * 100) : 100;

  const fleetLostMWh = rows.reduce((acc, r) => acc + r.impact.lostMWh, 0);
  const fleetRevenueRisk = rows.reduce((acc, r) => acc + r.impact.revenueAtRiskGbp, 0);
  const f = FARM[farm];

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>{f.name} <span className="muted" style={{ fontWeight: 500 }}>· {f.type}</span></h1>
          <p className="sub">{f.why[0].toUpperCase() + f.why.slice(1)}. Fleet-level telemetry and early-warning risk monitoring.</p>
        </div>
        <div className="actions">
          <div className="seg" role="group" aria-label="Farm">
            <Link className="btn sm" href="/farms/kelmarsh/" aria-current={farm === "kelmarsh" ? "page" : undefined} style={farm === "kelmarsh" ? { background: "var(--accent-soft)", borderColor: "var(--accent-line)" } : { border: 0 }}>Kelmarsh</Link>
            <Link className="btn sm" href="/farms/penmanshiel/" aria-current={farm === "penmanshiel" ? "page" : undefined} style={farm === "penmanshiel" ? { background: "var(--accent-soft)", borderColor: "var(--accent-line)" } : { border: 0 }}>Penmanshiel</Link>
          </div>
          <Link className="btn sm" href={`/windows/`}>All windows <IconArrow /></Link>
        </div>
      </div>

      <div className="kpis">
        <div className="card kpi">
          <span className="v">{turbines.length}</span>
          <span className="l">turbines active</span>
          <span className="c">{criticalCount > 0 ? `${criticalCount} require immediate triage` : "fleet operational"}</span>
        </div>
        <div className="card kpi">
          <span className="v num">{fmtMWh(fleetLostMWh)}</span>
          <span className="l">generation at risk</span>
          <span className="c">potential unscheduled downtime</span>
        </div>
        <div className="card kpi">
          <span className="v num" style={{ color: fleetRevenueRisk > 0 ? "#dc2626" : undefined }}>
            {fmtGbp(fleetRevenueRisk)}
          </span>
          <span className="l">revenue at risk</span>
          <span className="c">@ £85/MWh wholesale</span>
        </div>
        <div className="card kpi">
          <span className="v">{alarms}</span>
          <span className="l">alarms raised</span>
          <span className="c">{criticalCount > 0 ? `${criticalCount} critical, ${advisoryCount} advisory` : "fleet operating nominally"}</span>
        </div>
        <div className="card kpi">
          <span className="v">{healthIndex}%</span>
          <span className="l">fleet health index</span>
          <span className="c">{nominalCount} / {turbines.length} turbines nominal</span>
        </div>
      </div>

      <FleetMap windows={windows} defaultFarm={farm} />
      <div className={styles.grid}>
        {rows.map(({ t, list, latest: w, impact }) => (
          <div key={t} className={`card ${styles.card}`}>
            <div className={styles.head}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <b>{tcode(w)}</b>
                <span
                  className="chip"
                  style={{
                    background:
                      impact.urgency === "critical"
                        ? "rgba(239, 68, 68, 0.12)"
                        : impact.urgency === "advisory"
                          ? "rgba(245, 158, 11, 0.12)"
                          : "rgba(16, 185, 129, 0.12)",
                    color:
                      impact.urgency === "critical"
                        ? "#dc2626"
                        : impact.urgency === "advisory"
                          ? "#d97706"
                          : "#059669",
                    fontWeight: 600,
                    fontSize: 11,
                    padding: "2px 6px",
                  }}
                >
                  {impact.urgency.toUpperCase()}
                </span>
              </div>
              <span className="num" style={{ fontSize: 12, color: "var(--ink-2)" }}>
                {impact.totalFinancialRiskGbp > 0 ? `${fmtGbp(impact.totalFinancialRiskGbp)} at risk` : f.type}
              </span>
            </div>
            <div className={styles.when}><span className="num">{w.anchor}</span> · asked {w.horizon_h} h ahead · {stateLabel(w.state)}</div>
            <div className={styles.risk}>
              <span className={`${styles.v} num`}>{pct(w.score)}</span>
              <div className="meter" role="img" aria-label={`P(fault stop) ${pct(w.score)}`}><i style={{ width: `${Math.round(w.score * 100)}%` }} /></div>
              <span className={styles.l}>P(fault stop) · {w.pred === "none" ? "no fault stop expected" : <b>{cls(w.pred)}</b>}</span>
            </div>
            <div className={styles.line}>
              <span className="label" style={{ marginRight: 4 }}>Status</span>
              <span className="mono" style={{ color: impact.urgency === "critical" ? "#dc2626" : impact.urgency === "advisory" ? "#d97706" : "var(--ink-2)" }}>
                {w.pred === "none" ? "Nominal operation · no trip risk" : `Precursor: ${cls(w.pred)}`}
              </span>
              <Link href={`/turbines/${farm}/${t}/`} className="btn sm" style={{ marginLeft: "auto", padding: "2px 8px", fontSize: 11 }}>
                Diagnose <IconArrow />
              </Link>
            </div>
            <div className={styles.hist}>
              <HistoryStrip list={list} />
              <div className={styles.cap}><span>{list.length} windows · {list[0].anchor.slice(0, 7)} → {w.anchor.slice(0, 7)}</span><Link href={`/turbines/${farm}/${t}/`}>details <IconArrow /></Link></div>
            </div>
          </div>
        ))}
      </div>
      <p className="legend">
        <span><i style={{ background: "var(--risk)" }} />P(fault stop) per sampled window</span>
        <span className="muted">Click any turbine card or bar to inspect SCADA telemetry.</span>
      </p>
    </div>
  );
}
