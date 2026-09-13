import type { Metadata } from "next";
import { notFound } from "next/navigation";

import FarmView from "@/components/FarmView";
import { allSummaries } from "@/lib/data";
import { FARM, FARMS } from "@/lib/labels";
import type { Farm } from "@/lib/types";

type Params = { params: Promise<{ farm: string }> };

export const dynamicParams = false;
export function generateStaticParams() { return FARMS.map((farm) => ({ farm })); }
export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { farm } = await params;
  return { title: FARM[farm as Farm]?.name ?? "Farm" };
}

export default async function FarmPage({ params }: Params) {
  const { farm } = await params;
  if (!FARMS.includes(farm as Farm)) notFound();
  return <FarmView farm={farm as Farm} windows={allSummaries()} />;
}
