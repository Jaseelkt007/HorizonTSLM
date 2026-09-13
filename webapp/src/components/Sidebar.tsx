"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import ThemeToggle from "./ThemeToggle";
import styles from "./Sidebar.module.css";

const I = {
  home: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 7.5 8 2.5l6 5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z"/><path d="M6.5 14V9.5h3V14"/></svg>,
  farm: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M8 6.5V15M5.5 15h5"/><path d="M8 6.5 5 2M8 6.5l5.2-1.2M8 6.5l-3 5.3"/><circle cx="8" cy="6.5" r="1"/></svg>,
  list: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M3 4h10M3 8h10M3 12h10"/></svg>,
  chart: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M2 13h12"/><path d="M3 10l3-3 3 2 4-5"/></svg>,
  results: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M3 13V8M8 13V3M13 13V6"/></svg>,
};

export default function Sidebar({ model, nWindows }: { model: string; nWindows: number }) {
  const p = usePathname() ?? "/";
  const cur = (test: boolean) => (test ? "page" : undefined);
  return (
    <aside className={styles.side}>
      <Link href="/" className={styles.brand}>
        <svg viewBox="0 0 34 34" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 14v18M13 32h8" />
          <g transform="translate(17 14)">
            <path d="M0 0 1.6-11.5Q0-13.5-1.6-11.5Z" fill="currentColor" stroke="none" />
            <path d="M0 0 1.6-11.5Q0-13.5-1.6-11.5Z" fill="currentColor" stroke="none" transform="rotate(120)" />
            <path d="M0 0 1.6-11.5Q0-13.5-1.6-11.5Z" fill="currentColor" stroke="none" transform="rotate(240)" />
            <circle r="2" fill="var(--side-bg)" />
          </g>
        </svg>
        <span><b>Turbine Alarm Explainer</b><small>Temporal AI Challenge</small></span>
      </Link>
      <nav className={styles.nav} aria-label="Main">
        <Link href="/" aria-current={cur(p === "/")}>{I.home}Overview</Link>
        <div className={styles.grp}>Data</div>
        <Link href="/farms/kelmarsh/" aria-current={cur(p.startsWith("/farms/kelmarsh"))}>{I.farm}Kelmarsh</Link>
        <Link href="/farms/penmanshiel/" aria-current={cur(p.startsWith("/farms/penmanshiel"))}>{I.farm}Penmanshiel</Link>
        <Link href="/windows/" aria-current={cur(p.startsWith("/windows"))}>{I.list}Windows</Link>
        <div className={styles.grp}>Model</div>
        <Link href="/window/" aria-current={cur(p.startsWith("/window/"))}>{I.chart}Signals &amp; answer</Link>
        <Link href="/results/" aria-current={cur(p.startsWith("/results"))}>{I.results}Results</Link>
      </nav>
      <div className={styles.foot}>
        <span>Headline model<br /><code>{model}</code></span>
        <span>{nWindows} held-out windows · Cubico SCADA, CC-BY-4.0</span>
        <ThemeToggle className={styles.theme} />
      </div>
    </aside>
  );
}
