/** Tiny inline line for a channel row. */
export default function Sparkline({ values, color = "var(--ink-3)", width = 64, height = 18 }: { values: number[]; color?: string; width?: number; height?: number }) {
  const n = values.length;
  let lo = Math.min(...values), hi = Math.max(...values);
  if (hi - lo < 1e-6) { hi = lo + 1; lo -= 1; }
  const d = values.map((v, i) => `${i ? "L" : "M"}${((i / (n - 1)) * (width - 2) + 1).toFixed(1)},${(1 + (1 - (v - lo) / (hi - lo)) * (height - 2)).toFixed(1)}`).join("");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth={1.2} strokeLinejoin="round" />
    </svg>
  );
}
