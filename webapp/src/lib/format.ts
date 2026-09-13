import { CLASS_LABEL, FARM } from "./labels";
import type { Claim, Question, WindowSummary } from "./types";

export const fmt = (x: number | null | undefined, d = 2): string =>
  x == null || Number.isNaN(Number(x)) ? "–" : Number(x).toFixed(d);

export const pct = (x: number | null | undefined): string =>
  x == null || Number.isNaN(Number(x)) ? "–" : `${Math.round(x * 100)} %`;

/** minutes → "6 h 03 min" / "45 min" */
export function dur(min: number | null | undefined): string {
  if (min == null) return "";
  const h = Math.floor(min / 60);
  const r = min % 60;
  if (!h) return `${r} min`;
  return r ? `${h} h ${String(r).padStart(2, "0")} min` : `${h} h`;
}

export const tcode = (w: { turbine: number }): string => `T${String(w.turbine).padStart(2, "0")}`;
export const tname = (w: { farm: keyof typeof FARM; turbine: number }): string =>
  `${FARM[w.farm].name} ${tcode(w)}`;
export const cls = (c: string): string => CLASS_LABEL[c] ?? c;
export const stateLabel = (s: string): string => (s === "producing" ? "producing" : "idle, low wind");

export interface ParsedAnswer {
  body: string;
  ans: string;
  label: string;
}

/** Split a generated text into the explanation body and its final `Answer:` line; parse the label from it. */
export function parseAnswer(text: string): ParsedAnswer {
  const cut = text.search(/Answer\s*:/i);
  const body = cut < 0 ? text : text.slice(0, cut);
  const ans = cut < 0 ? "" : text.slice(cut).trim();
  const m = ans.match(/Answer\s*:\s*(?:yes\s*,\s*)?([a-z_]+)/i);
  let label = m ? m[1].toLowerCase() : "";
  if (label === "no") label = "none";
  return { body: body.trimEnd(), ans, label };
}

export const isRight = (w: WindowSummary, q: Question = "t1"): boolean =>
  (q === "t1" ? w.pred : (w.t3_pred ?? "")) === w.gold;

/** How well an explanation's numbers verify: verified minus twice the wrong ones. */
export const verifyScore = (w: { n_ok: number; n_claims: number }): number =>
  w.n_ok - 2 * (w.n_claims - w.n_ok);

export const okCount = (claims: Claim[] | null | undefined): number =>
  (claims ?? []).filter((c) => c.ok).length;

/** The window key used by the turbine filter: "farm|turbine". */
export const turbineKey = (w: { farm: string; turbine: number }): string => `${w.farm}|${w.turbine}`;
