import { dur } from "@/lib/format";
import type { WindowSummary } from "@/lib/types";

/** The 24 h window, the horizon the model was asked about, and where the stop actually began. */
export default function Timeline({ w }: { w: Pick<WindowSummary, "horizon_h" | "gold" | "outcome"> }) {
  const H = w.horizon_h * 60;
  const lead = w.gold === "none" ? null : w.outcome.lead_time_min;
  const W = 420, Hh = 66, pl = 8, pr = 118, y = 32;
  const tmax = Math.max(H, lead ?? 0) * 1.12;
  const span = 1440 + tmax;
  const X = (m: number) => pl + ((m + 1440) / span) * (W - pl - pr);
  const f = (v: number) => v.toFixed(1);
  return (
    <svg viewBox={`0 0 ${W} ${Hh}`} role="img" aria-label={`Timeline: 24 h window, then the ${w.horizon_h} h horizon${lead != null ? `, stop at ${dur(lead)}` : ""}`}>
      <rect x={f(X(-1440))} y={y - 7} width={f(X(0) - X(-1440))} height={14} rx={2} fill="var(--series)" opacity={0.85} />
      <rect x={f(X(-60))} y={y - 7} width={f(X(0) - X(-60))} height={14} fill="var(--band)" />
      <rect x={f(X(0))} y={y - 7} width={f(Math.max(2, X(H) - X(0)))} height={14} rx={2} fill="var(--accent-soft)" stroke="var(--accent-line)" strokeWidth={1} />
      <line x1={f(X(0))} x2={f(X(0))} y1={y - 15} y2={y + 15} stroke="var(--ink)" strokeWidth={1.5} />
      <text x={f(X(-1440))} y={y - 15} fontSize={11} fill="var(--ink-2)">24 h of signals</text>
      <text x={f(X(0) + 3)} y={y - 15} fontSize={11} fill="var(--accent-ink)">asked: next {w.horizon_h} h</text>
      <text x={f(X(0) - 4)} y={y + 27} fontSize={11} textAnchor="end" fill="var(--ink)" fontWeight={600}>now</text>
      {lead != null ? (
        <>
          <line x1={f(X(lead))} x2={f(X(lead))} y1={y - 11} y2={y + 11} stroke="var(--crit)" strokeWidth={2.5} strokeLinecap="round" />
          <circle cx={f(X(lead))} cy={y - 11} r={3.5} fill="var(--crit)" />
          <text x={f(X(lead) + 5)} y={y + 27} fontSize={11} fill="var(--crit)" fontWeight={600}>stop at +{dur(lead)}</text>
        </>
      ) : (
        <text x={f(X(H) + 5)} y={y + 27} fontSize={11} fill="var(--ink-2)">no fault stop</text>
      )}
    </svg>
  );
}
