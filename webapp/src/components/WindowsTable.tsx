"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { cls, pct, tname, turbineKey } from "@/lib/format";
import { computeImpact, fmtMWh } from "@/lib/impact";
import { CLASS_SHORT, FARM } from "@/lib/labels";
import type { WindowSummary } from "@/lib/types";

import { IconArrow } from "./Icons";
import styles from "./WindowsTable.module.css";

type Sort = "recent" | "risk" | "mwh";
interface Filters { farm: string; turbine: string; status: string; cls: string }
const EMPTY: Filters = { farm: "", turbine: "", status: "", cls: "" };

export default function WindowsTable({ summaries }: { summaries: WindowSummary[] }) {
  const router = useRouter();
  const turbineParam = useSearchParams().get("turbine") ?? "";
  const [filters, setFilters] = useState<Filters>(() => (turbineParam ? { ...EMPTY, farm: turbineParam.split("|")[0], turbine: turbineParam } : EMPTY));
  const [sort, setSort] = useState<Sort>("recent");

  const turbines = useMemo(() => {
    const keys = [...new Set(summaries.filter((w) => !filters.farm || w.farm === filters.farm).map(turbineKey))];
    return keys.sort((a, b) => { const [fa, ta] = a.split("|"); const [fb, tb] = b.split("|"); return fa.localeCompare(fb) || +ta - +tb; });
  }, [summaries, filters.farm]);

  const classes = useMemo(
    () => [...new Set(summaries.map((w) => w.pred).filter((g) => g !== "none"))].sort(),
    [summaries],
  );

  const rows = useMemo(() => {
    const f = filters;
    const out = summaries.filter(
      (w) =>
        (!f.farm || w.farm === f.farm) &&
        (!f.turbine || turbineKey(w) === f.turbine) &&
        (!f.status || (f.status === "critical" ? w.score >= 0.5 : f.status === "advisory" ? (w.score >= 0.35 && w.score < 0.5) : w.score < 0.35)) &&
        (!f.cls || w.pred === f.cls),
    );
    const byDate = (a: WindowSummary, b: WindowSummary) => b.anchor.localeCompare(a.anchor);
    if (sort === "risk") out.sort((a, b) => b.score - a.score || byDate(a, b));
    else if (sort === "mwh") out.sort((a, b) => computeImpact(b).lostMWh - computeImpact(a).lostMWh || byDate(a, b));
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
            <option value="">all farms</option>
            <option value="kelmarsh">Kelmarsh</option>
            <option value="penmanshiel">Penmanshiel</option>
          </select>
        </label>
        <label className="f">Turbine
          <select value={filters.turbine} onChange={set("turbine")}>
            <option value="">any turbine</option>
            {turbines.map((k) => { const [fa, t] = k.split("|"); return <option key={k} value={k}>{filters.farm ? "" : `${FARM[fa as keyof typeof FARM].name} `}T{String(t).padStart(2, "0")}</option>; })}
          </select>
        </label>
        <label className="f">Operational Status
          <select value={filters.status} onChange={set("status")}>
            <option value="">all statuses</option>
            <option value="critical">Critical Trip Risk (P ≥ 0.5)</option>
            <option value="advisory">Advisory Alert (P ≥ 0.35)</option>
            <option value="nominal">Nominal Operation</option>
          </select>
        </label>
        <label className="f">Subsystem
          <select value={filters.cls} onChange={set("cls")}>
            <option value="">all subsystems</option>
            {classes.map((c) => <option key={c} value={c}>{cls(c)}</option>)}
          </select>
        </label>
        <label className="f">Sort
          <select value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="recent">most recent</option>
            <option value="risk">highest trip risk</option>
            <option value="mwh">highest MWh exposure</option>
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
              <th>Turbine</th>
              <th>Timestamp</th>
              <th>Horizon</th>
              <th>Subsystem Assessment</th>
              <th className="r">P(trip)</th>
              <th className="r">MWh at Risk</th>
              <th>Urgency Status</th>
              <th className="r">Diagnostics</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((w) => {
              const impact = computeImpact(w);
              const isCrit = w.score >= 0.5;
              const isAdv = w.score >= 0.35 && !isCrit;
              return (
                <tr key={w.id} className="link" onClick={() => router.push(`/turbines/${w.farm}/${w.turbine}`)}>
                  <td>
                    <Link className={styles.t} href={`/turbines/${w.farm}/${w.turbine}`} onClick={(e) => e.stopPropagation()}>
                      {tname(w)}
                    </Link>
                    <div className={styles.sub}>{FARM[w.farm].tag}</div>
                  </td>
                  <td className="num">{w.anchor}</td>
                  <td>+{w.horizon_h} h lead</td>
                  <td>
                    {w.pred === "none" ? (
                      <span className="chip neutral">Nominal Envelope</span>
                    ) : (
                      <span className="chip class" title={cls(w.pred)}>
                        {CLASS_SHORT[w.pred] ?? w.pred}
                      </span>
                    )}
                  </td>
                  <td className="r num" style={{ color: isCrit ? "#dc2626" : undefined, fontWeight: isCrit ? 600 : 400 }}>
                    {pct(w.score)}
                  </td>
                  <td className="r num">{impact.lostMWh > 0 ? fmtMWh(impact.lostMWh) : "–"}</td>
                  <td>
                    <span
                      className="chip"
                      style={{
                        background: isCrit ? "rgba(239, 68, 68, 0.12)" : isAdv ? "rgba(245, 158, 11, 0.12)" : "rgba(16, 185, 129, 0.12)",
                        color: isCrit ? "#dc2626" : isAdv ? "#d97706" : "#059669",
                        fontWeight: 600,
                        fontSize: 11,
                      }}
                    >
                      {isCrit ? "CRITICAL" : isAdv ? "ADVISORY" : "NOMINAL"}
                    </span>
                  </td>
                  <td className="r">
                    <Link href={`/turbines/${w.farm}/${w.turbine}`} className="btn sm">
                      Diagnose <IconArrow />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
