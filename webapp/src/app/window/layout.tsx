import { Suspense } from "react";

import WindowRail from "@/components/WindowRail";
import styles from "@/components/Window.module.css";
import { allSummaries, showcaseId } from "@/lib/data";

export default function WindowLayout({ children }: { children: React.ReactNode }) {
  return (
    <section className="view" aria-label="Window">
      <div className={styles.explore}>
        <Suspense fallback={null}>
          <WindowRail summaries={allSummaries()} showcaseId={showcaseId()} />
        </Suspense>
        <div className={styles.detail}>{children}</div>
      </div>
    </section>
  );
}
