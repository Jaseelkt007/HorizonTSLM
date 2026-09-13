import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import WindowView from "@/components/WindowView";
import { getWindow, loadDemo, neighbors } from "@/lib/data";
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
  const { prev, next } = neighbors(id);
  return (
    <Suspense fallback={null}>
      <WindowView w={w} meta={loadDemo().meta.channels} prev={prev} next={next} />
    </Suspense>
  );
}
