/** Build-time data access. Only server components import this (it reads the JSON files with fs). */
import fs from "node:fs";
import path from "node:path";

import { parseAnswer } from "./format";
import type { DemoData, ResultsSummary, WindowRecord, WindowSummary } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");

let demo: DemoData | undefined;
let results: ResultsSummary | undefined;

export function loadDemo(): DemoData {
  demo ??= JSON.parse(fs.readFileSync(path.join(DATA_DIR, "demo_data.json"), "utf8")) as DemoData;
  return demo;
}

export function loadResults(): ResultsSummary {
  results ??= JSON.parse(
    fs.readFileSync(path.join(DATA_DIR, "results_summary.json"), "utf8"),
  ) as ResultsSummary;
  return results;
}

export function summarize(w: WindowRecord): WindowSummary {
  return {
    id: w.id,
    farm: w.farm,
    turbine: w.turbine,
    anchor: w.anchor,
    horizon_h: w.horizon_h,
    split: w.split,
    state: w.state,
    gold: w.gold,
    pred: w.pred,
    score: w.score,
    outcome: w.outcome,
    n_claims: w.claims.length,
    n_ok: w.claims.filter((c) => c.ok).length,
    t3_pred: w.t3_text ? parseAnswer(w.t3_text).label : null,
  };
}

export function allSummaries(): WindowSummary[] {
  return loadDemo().windows.map(summarize);
}

export function getWindow(id: string): WindowRecord | undefined {
  return loadDemo().windows.find((w) => w.id === id);
}

/** The window the demo opens on: a Kelmarsh active precursor alarm with verified SCADA telemetry claims. */
export function showcaseId(): string {
  const ws = loadDemo().windows;
  const allOk = (cs: { ok: boolean }[] | null) => !!cs && cs.length > 0 && cs.every((c) => c.ok);
  const ranked = ws
    .filter((w) => w.farm === "kelmarsh" && w.pred !== "none" && w.score >= 0.5 && w.t3_text && allOk(w.claims) && allOk(w.t3_claims))
    .sort((a, b) => b.claims.length + (b.t3_claims?.length ?? 0) - (a.claims.length + (a.t3_claims?.length ?? 0)) || a.anchor.localeCompare(b.anchor));
  return (ranked[0] ?? ws.find((w) => w.pred !== "none" && w.score >= 0.5) ?? ws[0]).id;
}

/** Previous / next sampled window of the same turbine, by date. */
export function neighbors(id: string): { prev?: string; next?: string } {
  const w = getWindow(id);
  if (!w) return {};
  const list = loadDemo()
    .windows.filter((x) => x.farm === w.farm && x.turbine === w.turbine)
    .sort((a, b) => a.anchor.localeCompare(b.anchor));
  const i = list.findIndex((x) => x.id === id);
  return { prev: list[i - 1]?.id, next: list[i + 1]?.id };
}
