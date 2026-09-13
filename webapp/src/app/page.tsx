import FarmOverviewClient from "@/components/FarmOverviewClient";
import { allSummaries } from "@/lib/data";

export default function OverviewPage() {
  const sums = allSummaries();

  return (
    <div className="page">
      <FarmOverviewClient windows={sums} />
    </div>
  );
}
