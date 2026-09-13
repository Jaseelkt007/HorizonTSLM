import type { Metadata } from "next";

import ResultsView from "@/components/ResultsView";
import { loadResults } from "@/lib/data";

export const metadata: Metadata = { title: "Results" };

export default function ResultsPage() {
  return <ResultsView results={loadResults()} />;
}
