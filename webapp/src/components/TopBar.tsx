import Link from "next/link";

import NavTabs from "./NavTabs";
import ThemeToggle from "./ThemeToggle";
import styles from "./TopBar.module.css";

export default function TopBar() {
  return (
    <header className={styles.top}>
      <Link href="/" className={styles.brand}>
        <svg viewBox="0 0 34 34" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 14v18M13 32h8" />
          <g transform="translate(17 14)">
            <path d="M0 0 1.6-11.5Q0-13.5-1.6-11.5Z" fill="currentColor" stroke="none" />
            <path d="M0 0 1.6-11.5Q0-13.5-1.6-11.5Z" fill="currentColor" stroke="none" transform="rotate(120)" />
            <path d="M0 0 1.6-11.5Q0-13.5-1.6-11.5Z" fill="currentColor" stroke="none" transform="rotate(240)" />
            <circle r="2" fill="var(--surface)" />
          </g>
        </svg>
        <div>
          <h1>Turbine Alarm Explainer</h1>
          <span className={styles.sub}>
            24 h of SCADA in; an early warning with its evidence out. Every number the model writes is checked against the signals it saw.
          </span>
        </div>
      </Link>
      <NavTabs className={styles.tabs} />
      <ThemeToggle className={styles.theme} />
    </header>
  );
}
