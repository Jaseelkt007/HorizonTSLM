"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { cls, dur, isRight, pct, tname, turbineKey, verifyScore } from "@/lib/format";
import { computeImpact, fmtMWh } from "@/lib/impact";
import { CLASS_SHORT, FARM } from "@/lib/labels";
import type { WindowSummary } from "@/lib/types";

import { VerdictChip } from "./Icons";
import styles from "./WindowsTable.module.css";

type Sort = "recent" | "verified" | "risk" | "mwh";
interface Filters { farm: string; turbine: string; gold: string; verdict: string; cls: string }
const EMPTY: Filters = { farm: "", turbine: "", gold: "", verdict: "", cls: "" };

export default function WindowsTable({ summaries }: { summaries: WindowSummary[] }) {
  const router = useRouter();
  const turbineParam = useSearchParams().get("turbine") ?? "";
  const [filters, setFilters] = useState<Filters>(() => (turbineParam ? { ...EMPTY, farm: turbineParam.split("|")[0], turbine: turbineParam } : EMPTY));
  const [sort, setSort] = useState<Sort>("recent");

  const turbines = useMemo(() => {
    const keys = [...new Set(summaries.filter((w) => !filters.farm || w.farm === filters.farm).map(turbineKey))];
    return keys.sort((a, b) => { const [fa, ta] = a.split("|"); const [fb, tb] = b.split("|"); return fa.localeCompare(fb) || +ta - +tb; });
  }, [summaries, filters.farm]);
  const classes = useMemo(() => [...new Set(summaries.map((w) => w.gold).filter((g) => g !== "none"))].sort(), [summaries]);
  const rows = useMemo(() => {
    const f = filters;
    const out = summaries.filter(
      (w) =>
        (!f.farm || w.farm === f.farm) &&
        (!f.turbine || turbineKey(w) === f.turbine) &&
        (!f.gold || (f.gold === "none" ? w.gold === "none" : w.gold !== "none")) &&
        (!f.verdict || (isRight(w) ? "right" : "wrong") === f.verdict) &&
        (!f.cls || w.gold === f.cls),
    );
    const byDate = (a: WindowSummary, b: WindowSummary) => b.anchor.localeCompare(a.anchor);
    if (sort === "risk") out.sort((a, b) => b.score - a.score || byDate(a, b));
    else if (sort === "mwh") out.sort((a, b) => computeImpact(b).lostMWh - computeImpact(a).lostMWh || byDate(a, b));
    else if (sort === "verified") out.sort((a, b) => verifyScore(b) - verifyScore(a) || byDate(a, b));
    else out.sort(byDate);
    return out;
  }, [summaries, filters, sort]);
  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    setFilters((f) => (k === "farm" ? { ...f, farm: e.target.value, turbine: "" } : { ...f, [k]: e.target.value }));
  const active = Object.values(filters).some(Boolean);

  return (
    <div className="card">
      <div className={styles.filters}>
        <label className="f">Farm
          <select value={filters.farm} onChange={set("farm")}>
            <option value="">both farms</option>
            <option value="kelmarsh">Kelmarsh · unseen farm</option>
            <option value="penmanshiel">Penmanshiel · unseen years</option>
          </select>
        </label>
        <label className="f">Turbine
          <select value={filters.turbine} onChange={set("turbine")}>
            <option value="">any</option>
            {turbines.map((k) => { const [fa, t] = k.split("|"); return <option key={k} value={k}>{filters.farm ? "" : `${FARM[fa as keyof typeof FARM].name} `}T{String(t).padStart(2, "0")}</option>; })}
          </select>
        </label>
        <label className="f">What followed
          <select value={filters.gold} onChange={set("gold")}>
            <option value="">anything</option>
            <option value="pos">a fault stop</option>
            <option value="none">no fault stop</option>
          </select>
        </label>
        <label className="f">Subsystem
          <select value={filters.cls} onChange={set("cls")}>
            <option value="">any</option>
            {classes.map((c) => <option key={c} value={c}>{cls(c)}</option>)}
          </select>
        </label>
        <label className="f">Model was
          <select value={filters.verdict} onChange={set("verdict")}>
            <option value="">right or wrong</option>
            <option value="right">right</option>
            <option value="wrong">wrong</option>
          </select>
        </label>
        <label className="f">Sort
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="recent">most recent</option>
            <option value="risk">highest risk</option>
            <option value="mwh">highest MWh at risk</option>
            <option value="verified">best-verified explanation</option>
          </select>
        </label>
        <div className={styles.count}>
          <span>{rows.length} of {summaries.length}</span>
          {active && <button type="button" className="btn sm" onClick={() => setFilters(EMPTY)}>Clear</button>}
        </div>
      </div>
      <div className={`table-wrap ${styles.tbl}`}>
        <table className="data">
          <thead>
            <tr>
              <th>Turbine</th><th>Window ending</th><th>Asked</th><th>Model answered</th><th className="r">P(fault)</th><th className="r">MWh at Risk</th><th>What followed</th><th>Numbers verified</th><th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((w) => {
              const impact = computeImpact(w);
              return (
                <tr key={w.id} className="link" onClick={() => router.push(`/window/${w.id}/`)}>
                  <td><Link className={styles.t} href={`/window/${w.id}/`} onClick={(e) => e.stopPropagation()}>{tname(w)}</Link><div className={styles.sub}>{FARM[w.farm].tag}</div></td>
                  <td className="num">{w.anchor}</td>
                  <td>{w.horizon_h} h ahead</td>
                  <td>{w.pred === "none" ? <span className="chip neutral">no fault stop</span> : <span className="chip class" title={cls(w.pred)}>{CLASS_SHORT[w.pred] ?? w.pred}</span>}</td>
                  <td className="r num">{pct(w.score)}</td>
                  <td className="r num">{impact.lostMWh > 0 ? fmtMWh(impact.lostMWh) : "–"}</td>
                  <td>{w.gold === "none" ? <span className="muted">no fault stop in {w.horizon_h} h</span> : <><span className="mono">{w.outcome.message ?? cls(w.gold)}</span> <span className="muted">+{dur(w.outcome.lead_time_min)}</span></>}</td>
                  <td><span className={styles.ver}><span className={styles.track}><i style={{ width: `${w.n_claims ? Math.round((w.n_ok / w.n_claims) * 100) : 0}%` }} /></span><span className="num">{w.n_ok} / {w.n_claims}</span></span></td>
                  <td><VerdictChip right={isRight(w)} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
