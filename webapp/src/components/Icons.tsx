export function IconCheck() {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 6.5 4.8 9 10 3.5" />
    </svg>
  );
}
export function IconX() {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M3 3l6 6M9 3l-6 6" />
    </svg>
  );
}
export function IconArrow() {
  return (
    <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: 11, height: 11 }}>
      <path d="M2 6h8M6.5 2.5 10 6l-3.5 3.5" />
    </svg>
  );
}

/** right / wrong: the answer line against the alarm log. */
export function VerdictChip({ right, long = false }: { right: boolean; long?: boolean }) {
  const text = right ? (long ? "matches the log" : "right") : long ? "does not match the log" : "wrong";
  return (
    <span className={`chip ${right ? "good" : "bad"}`} title={right ? "the answer line matches the alarm log" : "the answer line does not match the alarm log"}>
      {right ? <IconCheck /> : <IconX />}
      {text}
    </span>
  );
}
