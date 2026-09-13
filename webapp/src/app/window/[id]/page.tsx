import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import WindowDetail from "@/components/WindowDetail";
import { getWindow, loadDemo } from "@/lib/data";
import { tname } from "@/lib/format";

type Params = { params: Promise<{ id: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return loadDemo().windows.map((w) => ({ id: w.id }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { id } = await params;
  const w = getWindow(id);
  return { title: w ? `${tname(w)}, ${w.anchor}` : "Window" };
}

export default async function WindowPage({ params }: Params) {
  const { id } = await params;
  const w = getWindow(id);
  if (!w) notFound();
  return (
    <Suspense fallback={null}>
      <WindowDetail w={w} meta={loadDemo().meta.channels} />
    </Suspense>
  );
}
