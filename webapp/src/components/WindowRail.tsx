"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";

import { cls, isRight, tname, turbineKey, verifyScore } from "@/lib/format";
import { CLASS_SHORT, FARM } from "@/lib/labels";
import type { WindowSummary } from "@/lib/types";

import styles from "./Window.module.css";

type Sort = "recent" | "verified" | "risk";
interface Filters { farm: string; turbine: string; gold: string; verdict: string; cls: string }
const EMPTY: Filters = { farm: "", turbine: "", gold: "", verdict: "", cls: "" };

/** Filterable list of the demo windows. Lives in the /window layout so its state survives navigation. */
export default function WindowRail({ summaries, showcaseId }: { summaries: WindowSummary[]; showcaseId: string }) {
  const pathname = usePathname() ?? "";
  const params = useSearchParams();
  const turbineParam = params.get("turbine") ?? "";
  const [filters, setFilters] = useState<Filters>(() => fromTurbine(turbineParam));
  const [sort, setSort] = useState<Sort>("recent");
  const [open, setOpen] = useState(false);

  // A link from the farm board carries ?turbine=farm|n: focus the list on that turbine (state adjusted during render,
  // the React-recommended way to react to a changed prop without an effect).
  const [seenTurbine, setSeenTurbine] = useState(turbineParam);
  if (turbineParam !== seenTurbine) {
    setSeenTurbine(turbineParam);
    if (turbineParam) setFilters(fromTurbine(turbineParam));
  }
  // On phones the list is a drawer; close it once a window has been chosen.
  const [seenPath, setSeenPath] = useState(pathname);
  if (pathname !== seenPath) {
    setSeenPath(pathname);
    setOpen(false);
  }

  const m = pathname.match(/^\/window\/([^/]+)/);
  const currentId = m ? decodeURIComponent(m[1]) : showcaseId;

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
    else if (sort === "verified") out.sort((a, b) => verifyScore(b) - verifyScore(a) || byDate(a, b));
    else out.sort(byDate);
    return out;
  }, [summaries, filters, sort]);

  const set = (k: keyof Filters) => (e: React.ChangeEvent<HTMLSelectElement>) =>
    setFilters((f) => (k === "farm" ? { ...f, farm: e.target.value, turbine: "" } : { ...f, [k]: e.target.value }));

  return (
    <aside className={`${styles.rail} ${open ? "" : styles.closed}`}>
      <button type="button" className={styles.toggle} aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span>Browse windows</span>
        <span className="muted">{rows.length} windows</span>
      </button>
      <div className={styles.body}>
        <div className={styles.filters}>
          <label className="f">Farm
            <select id="f-farm" value={filters.farm} onChange={set("farm")}>
              <option value="">both farms</option>
              <option value="kelmarsh">Kelmarsh · unseen farm</option>
              <option value="penmanshiel">Penmanshiel · unseen years</option>
            </select>
          </label>
          <label className="f">Turbine
            <select id="f-turbine" value={filters.turbine} onChange={set("turbine")}>
              <option value="">any</option>
              {turbines.map((k) => { const [fa, t] = k.split("|"); return <option key={k} value={k}>{filters.farm ? "" : `${FARM[fa as keyof typeof FARM].name} `}T{String(t).padStart(2, "0")}</option>; })}
            </select>
          </label>
          <label className="f">What followed
            <select id="f-gold" value={filters.gold} onChange={set("gold")}>
              <option value="">anything</option>
              <option value="pos">a fault stop</option>
              <option value="none">no fault stop</option>
            </select>
          </label>
          <label className="f">Model was
            <select id="f-verdict" value={filters.verdict} onChange={set("verdict")}>
              <option value="">right or wrong</option>
              <option value="right">right</option>
              <option value="wrong">wrong</option>
            </select>
          </label>
          <label className="f">Subsystem
            <select id="f-class" value={filters.cls} onChange={set("cls")}>
              <option value="">any</option>
              {classes.map((c) => <option key={c} value={c}>{cls(c)}</option>)}
            </select>
          </label>
          <label className="f">Sort
            <select id="f-sort" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="recent">most recent</option>
              <option value="verified">best-verified explanation</option>
              <option value="risk">highest risk</option>
            </select>
          </label>
        </div>
        <div className={styles.count}>
          <span>{rows.length} of {summaries.length} windows</span>
          {(filters !== EMPTY && Object.values(filters).some(Boolean)) && (
            <button type="button" className="chip neutral" onClick={() => setFilters(EMPTY)} style={{ border: 0, cursor: "pointer" }}>clear filters</button>
          )}
        </div>
        <ul className={styles.list} aria-label="Windows">
          {rows.map((w) => {
            const right = isRight(w);
            return (
              <li key={w.id}>
                <Link href={`/window/${w.id}/`} className={styles.item} aria-current={w.id === currentId ? "page" : undefined}>
                  <span className={styles.t}>{tname(w)}</span>
                  <span className={`${styles.v} ${right ? styles.good : styles.bad}`} title={right ? "model was right" : "model was wrong"} />
                  <span className={styles.m}><b className="num">{w.anchor}</b> · {w.horizon_h} h ahead</span>
                  {w.gold === "none" ? <span className="chip neutral">quiet</span> : <span className="chip class" title={cls(w.gold)}>{CLASS_SHORT[w.gold] ?? w.gold}</span>}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}

function fromTurbine(key: string): Filters {
  if (!key) return EMPTY;
  const [farm] = key.split("|");
  return { ...EMPTY, farm, turbine: key };
}
