"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { cls, dur, isRight, pct, stateLabel, tcode, turbineKey } from "@/lib/format";
import { FARM, FARMS } from "@/lib/labels";
import type { Farm, WindowSummary } from "@/lib/types";

import styles from "./FarmBoard.module.css";
import HistoryStrip from "./HistoryStrip";
import { VerdictChip } from "./Icons";

export default function FarmBoard({ windows }: { windows: WindowSummary[] }) {
  const [farm, setFarm] = useState<Farm>("kelmarsh");
  const router = useRouter();

  const ws = useMemo(() => windows.filter((w) => w.farm === farm), [windows, farm]);
  const rows = useMemo(() => {
    const turbines = [...new Set(ws.map((w) => w.turbine))].sort((a, b) => a - b);
    return turbines
      .map((t) => {
        const list = ws.filter((w) => w.turbine === t).sort((a, b) => a.anchor.localeCompare(b.anchor));
        return { t, list, latest: list[list.length - 1] };
      })
      .sort((a, b) => b.latest.score - a.latest.score || a.t - b.t);
  }, [ws]);

  const pos = ws.filter((w) => w.gold !== "none").length;
  const ok = ws.filter((w) => isRight(w)).length;
  const alarms = ws.filter((w) => w.pred !== "none").length;
  const stats: [string, string][] = [
    [String(rows.length), "turbines sampled"],
    [String(ws.length), "held-out windows"],
    [String(pos), "followed by a fault stop"],
    [`${ok} / ${ws.length}`, "model right"],
    [String(alarms), "alarms raised"],
  ];
  const open = (w: WindowSummary) => router.push(`/window/${w.id}/?turbine=${encodeURIComponent(turbineKey(w))}`);

  return (
    <section className="view" aria-label="Farm board">
      <div className={styles.farmbar}>
        <div className="seg" role="group" aria-label="Farm">
          {FARMS.map((f) => (
            <button key={f} type="button" aria-pressed={f === farm} onClick={() => setFarm(f)}>
              {FARM[f].name}
              <small>
                {FARM[f].tag} · {windows.filter((w) => w.farm === f).length} windows
              </small>
            </button>
          ))}
        </div>
        <div className={styles.stats}>
          {stats.map(([v, l]) => (
            <div key={l} className={styles.stat}>
              <b className="num">{v}</b>
              <span>{l}</span>
            </div>
          ))}
        </div>
      </div>
      <p className="lede">
        {FARM[farm].name}, {FARM[farm].type}: {FARM[farm].why}. Each row shows the model&apos;s most recent sampled window for that turbine and its
        whole sampled history. The {windows.length} windows on this site are a curated sample of the held-out sets (well-verified alarms, quiet
        windows and some misses); the Results page scores the full sets.
      </p>
      <div className={`panel ${styles.board}`}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Turbine</th>
              <th>Latest sampled window</th>
              <th>Risk</th>
              <th>Subsystem named</th>
              <th>What followed</th>
              <th>Sampled history</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ t, list, latest: w }) => {
              const o = w.outcome;
              return (
                <tr key={t} className={styles.row} onClick={() => open(w)}>
                  <td>
                    <Link className={styles.tname} href={`/window/${w.id}/?turbine=${encodeURIComponent(turbineKey(w))}`} onClick={(e) => e.stopPropagation()}>
                      {tcode(w)}
                      <small>{FARM[w.farm].type}</small>
                    </Link>
                  </td>
                  <td data-l="Latest sampled window">
                    <span className="num">{w.anchor}</span>
                    <br />
                    <span className="muted">
                      asked {w.horizon_h} h ahead · {stateLabel(w.state)}
                    </span>
                  </td>
                  <td data-l="Risk">
                    <div className={styles.risk}>
                      <div className="meter" role="img" aria-label={`P(fault stop) ${pct(w.score)}`}>
                        <i style={{ width: `${Math.round(w.score * 100)}%` }} />
                      </div>
                      <b className="num">{pct(w.score)}</b>
                    </div>
                  </td>
                  <td data-l="Subsystem named">
                    {w.pred === "none" ? <span className="chip neutral">no fault stop expected</span> : <span className="chip class">{cls(w.pred)}</span>}
                  </td>
                  <td data-l="What followed">
                    {w.gold === "none" ? (
                      <span className="muted">no fault stop in the next {w.horizon_h} h</span>
                    ) : (
                      <>
                        <span className="mono">{o.message ?? cls(w.gold)}</span> <span className="muted">{dur(o.lead_time_min)} later</span>
                      </>
                    )}{" "}
                    <VerdictChip right={isRight(w)} />
                  </td>
                  <td data-l="Sampled history">
                    <div className={styles.hist}>
                      <HistoryStrip list={list} />
                      <div className={styles.cap}>
                        {list.length} windows, {list[0].anchor.slice(0, 7)} → {w.anchor.slice(0, 7)}
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="legend">
        <span>
          <i style={{ background: "var(--risk)" }} />
          bar height = the model&apos;s P(fault stop) for that window
        </span>
        <span>
          <i className="dot" style={{ background: "var(--ink)" }} />a fault stop did follow
        </span>
        <span className="muted">Click a turbine or a bar to open the window.</span>
      </p>
    </section>
  );
}
