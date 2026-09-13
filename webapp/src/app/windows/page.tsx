import type { Metadata } from "next";
import { Suspense } from "react";

import WindowsTable from "@/components/WindowsTable";
import { allSummaries } from "@/lib/data";

export const metadata: Metadata = { title: "Windows" };

export default function WindowsPage() {
  const ws = allSummaries();
  const pos = ws.filter((w) => w.gold !== "none").length;
  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>Held-out windows</h1>
          <p className="sub">{ws.length} windows the model never trained on · {pos} followed by a fault stop, {ws.length - pos} quiet.</p>
        </div>
      </div>
      <Suspense fallback={null}>
        <WindowsTable summaries={ws} />
      </Suspense>
    </div>
  );
}
