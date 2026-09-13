import type { Claim } from "@/lib/types";

/** The explanation body with every numeric claim marked verified (ok) or wrong against the window. */
export default function Explanation({ body, claims, className }: { body: string; claims: Claim[]; className?: string }) {
  const parts: React.ReactNode[] = [];
  let pos = 0;
  for (const c of claims) {
    if (c.start < pos || c.end > body.length) continue;
    if (c.start > pos) parts.push(body.slice(pos, c.start));
    parts.push(
      <mark key={c.start} className={c.ok ? undefined : "bad"} title={c.ok ? "verified against the window" : "does not match the window"}>
        {body.slice(c.start, c.end)}
      </mark>,
    );
    pos = c.end;
  }
  if (pos < body.length) parts.push(body.slice(pos));
  return <p className={className}>{parts}</p>;
}
