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

/** The window the demo opens on: a Kelmarsh alarm the model got right with every number verified. */
export function showcaseId(): string {
  const ws = loadDemo().windows;
  const show =
    ws.find(
      (w) =>
        w.farm === "kelmarsh" &&
        w.gold !== "none" &&
        w.pred === w.gold &&
        w.claims.length >= 4 &&
        w.claims.every((c) => c.ok),
    ) ?? ws[0];
  return show.id;
}
