import FarmBoard from "@/components/FarmBoard";
import { allSummaries } from "@/lib/data";

export default function FarmPage() {
  return <FarmBoard windows={allSummaries()} />;
}
