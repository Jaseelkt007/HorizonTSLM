import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import TurbineDetailView from "@/components/TurbineDetailView";
import { allSummaries, loadDemo } from "@/lib/data";
import { tname } from "@/lib/format";
import type { Farm } from "@/lib/types";

type Params = { params: Promise<{ farm: string; id: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  const windows = loadDemo().windows;
  const pairs = new Set<string>();
  windows.forEach((w) => pairs.add(`${w.farm}|${w.turbine}`));
  return Array.from(pairs).map((p) => {
    const [farm, id] = p.split("|");
    return { farm, id };
  });
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { farm, id } = await params;
  const turbineNum = parseInt(id, 10);
  return { title: `${tname({ farm: farm as Farm, turbine: turbineNum })} — Turbine Diagnostics` };
}

export default async function TurbinePage({ params }: Params) {
  const { farm: farmParam, id: idParam } = await params;
  const farm = farmParam as Farm;
  const turbineNum = parseInt(idParam, 10);

  const demo = loadDemo();
  const allWindows = demo.windows;
  const turbineRecords = allWindows.filter((w) => w.farm === farm && w.turbine === turbineNum);

  if (turbineRecords.length === 0) {
    notFound();
  }

  // Prioritize a window with a real fault stop or highest verified claims for the showcase
  const preferredRecord =
    turbineRecords.find((w) => w.gold !== "none" && w.pred === w.gold) ||
    turbineRecords.find((w) => w.gold !== "none") ||
    turbineRecords[0];

  const farmTurbines = [...new Set(allWindows.filter((w) => w.farm === farm).map((w) => w.turbine))].sort(
    (a, b) => a - b,
  );
  const curIdx = farmTurbines.indexOf(turbineNum);
  const prevTurbine = curIdx > 0 ? farmTurbines[curIdx - 1] : undefined;
  const nextTurbine = curIdx < farmTurbines.length - 1 ? farmTurbines[curIdx + 1] : undefined;

  const summaries = allSummaries().filter((w) => w.farm === farm);

  return (
    <Suspense fallback={null}>
      <TurbineDetailView
        turbine={turbineNum}
        farm={farm}
        meta={demo.meta.channels}
        currentRecord={preferredRecord}
        turbineRecords={turbineRecords}
        farmWindows={summaries}
        prevTurbine={prevTurbine}
        nextTurbine={nextTurbine}
      />
    </Suspense>
  );
}
