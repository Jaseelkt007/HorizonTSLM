/** Time axis helpers. Anchors are "YYYY-MM-DD HH:MM" in site-local time; we treat them as UTC so nothing shifts. */

export const STEP_MIN = 10;
export const N_STEPS = 144;

export function parseAnchor(anchor: string): Date {
  const m = anchor.match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
  if (!m) return new Date(NaN);
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]));
}

/** Minutes relative to the anchor for sample i (i = 143 is "now"). */
export const stepOffset = (i: number, n = N_STEPS): number => -(n - 1 - i) * STEP_MIN;

export const atOffset = (anchor: Date, min: number): Date => new Date(anchor.getTime() + min * 60_000);

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
export const fmtClock = (d: Date): string => `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
export const fmtDay = (d: Date): string => `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
export const fmtDateTime = (d: Date): string => `${fmtDay(d)} ${fmtClock(d)}`;

export interface TimeTick { min: number; label: string; day?: string }

/** Clock-aligned ticks every `stepH` hours across [fromMin, toMin] (minutes relative to the anchor). */
export function timeTicks(anchor: Date, fromMin: number, toMin: number, stepH = 3): TimeTick[] {
  const out: TimeTick[] = [];
  const first = atOffset(anchor, fromMin);
  // first clock hour that is a multiple of stepH at or after `first`
  const start = new Date(first);
  start.setUTCMinutes(0, 0, 0);
  while (start.getUTCHours() % stepH !== 0 || start < first) start.setUTCHours(start.getUTCHours() + 1);
  let lastDay = -1;
  for (let t = new Date(start); t.getTime() <= anchor.getTime() + toMin * 60_000; t = new Date(t.getTime() + stepH * 3_600_000)) {
    const min = (t.getTime() - anchor.getTime()) / 60_000;
    const day = t.getUTCDate();
    out.push({ min, label: fmtClock(t), day: day !== lastDay ? fmtDay(t) : undefined });
    lastDay = day;
  }
  return out;
}

/** d3-style "nice" ticks for a value axis. */
export function niceTicks(lo: number, hi: number, count = 4): number[] {
  if (!(hi > lo)) return [lo];
  const span = hi - lo;
  const raw = span / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}

export const fmtTick = (v: number): string =>
  Math.abs(v) >= 1000 ? v.toLocaleString("en-GB", { maximumFractionDigits: 0 }) : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2);

export const fmtValue = (v: number): string =>
  Math.abs(v) >= 1000 ? v.toLocaleString("en-GB", { maximumFractionDigits: 0 }) : Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2);
