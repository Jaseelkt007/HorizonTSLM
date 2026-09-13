import Link from "next/link";

import { cls, dur, isRight, pct, stateLabel, tcode, turbineKey } from "@/lib/format";
import { FARM } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import styles from "./FarmView.module.css";
import HistoryStrip from "./HistoryStrip";
import { IconArrow, VerdictChip } from "./Icons";

export default function FarmView({ farm, windows }: { farm: Farm; windows: WindowSummary[] }) {
  const ws = windows.filter((w) => w.farm === farm);
  const turbines = [...new Set(ws.map((w) => w.turbine))].sort((a, b) => a - b);
  const rows = turbines
    .map((t) => { const list = ws.filter((w) => w.turbine === t).sort((a, b) => a.anchor.localeCompare(b.anchor)); return { t, list, latest: list[list.length - 1] }; })
    .sort((a, b) => b.latest.score - a.latest.score || a.t - b.t);
  const pos = ws.filter((w) => w.gold !== "none").length;
  const ok = ws.filter((w) => isRight(w)).length;
  const alarms = ws.filter((w) => w.pred !== "none").length;
  const f = FARM[farm];
  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>{f.name} <span className="muted" style={{ fontWeight: 500 }}>· {f.type}</span></h1>
          <p className="sub">{f.why[0].toUpperCase() + f.why.slice(1)}. One card per turbine, latest sampled window first.</p>
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
        <div className="card kpi"><span className="v">{turbines.length}</span><span className="l">turbines sampled</span></div>
        <div className="card kpi"><span className="v">{ws.length}</span><span className="l">held-out windows</span></div>
        <div className="card kpi"><span className="v">{pos}</span><span className="l">followed by a fault stop</span></div>
        <div className="card kpi"><span className="v">{alarms}</span><span className="l">alarms the model raised</span></div>
        <div className="card kpi"><span className="v">{ok} <span className="muted" style={{ fontSize: 16, fontWeight: 500 }}>/ {ws.length}</span></span><span className="l">answers matching the log</span></div>
      </div>
      <div className={styles.grid}>
        {rows.map(({ t, list, latest: w }) => (
          <div key={t} className={`card ${styles.card}`}>
            <div className={styles.head}><b>{tcode(w)}</b><span>{f.type}</span></div>
            <div className={styles.when}><span className="num">{w.anchor}</span> · asked {w.horizon_h} h ahead · {stateLabel(w.state)}</div>
            <div className={styles.risk}>
              <span className={`${styles.v} num`}>{pct(w.score)}</span>
              <div className="meter" role="img" aria-label={`P(fault stop) ${pct(w.score)}`}><i style={{ width: `${Math.round(w.score * 100)}%` }} /></div>
              <span className={styles.l}>P(fault stop) · {w.pred === "none" ? "no fault stop expected" : <b>{cls(w.pred)}</b>}</span>
            </div>
            <div className={styles.line}>
              <span className="label" style={{ marginRight: 4 }}>Followed</span>
              {w.gold === "none" ? <span>no fault stop in {w.horizon_h} h</span> : <><span className="mono">{w.outcome.message ?? cls(w.gold)}</span><span className="muted">+{dur(w.outcome.lead_time_min)}</span></>}
              <VerdictChip right={isRight(w)} />
            </div>
            <div className={styles.hist}>
              <HistoryStrip list={list} />
              <div className={styles.cap}><span>{list.length} windows · {list[0].anchor.slice(0, 7)} → {w.anchor.slice(0, 7)}</span><Link href={`/windows/?turbine=${encodeURIComponent(turbineKey(w))}`}>list <IconArrow /></Link></div>
            </div>
          </div>
        ))}
      </div>
      <p className="legend">
        <span><i style={{ background: "var(--risk)" }} />P(fault stop) per sampled window</span>
        <span><i className="dot" style={{ background: "var(--ink)" }} />a fault stop followed</span>
        <span className="muted">Click a bar to open it.</span>
      </p>
    </div>
  );
}
