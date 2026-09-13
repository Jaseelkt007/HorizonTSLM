import type { Metadata } from "next";
import { Suspense } from "react";

import WindowsTable from "@/components/WindowsTable";
import { allSummaries } from "@/lib/data";

export const metadata: Metadata = { title: "SCADA Event Journal" };

export default function WindowsPage() {
  const ws = allSummaries();
  const alertsCount = ws.filter((w) => w.score >= 0.35).length;
  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>SCADA Event Journal</h1>
          <p className="sub">{ws.length} operational telemetry windows · {alertsCount} advisory &amp; critical alerts detected across fleet.</p>
        </div>
      </div>
      <Suspense fallback={null}>
        <WindowsTable summaries={ws} />
      </Suspense>
    </div>
  );
}
