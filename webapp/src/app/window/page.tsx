import { Suspense } from "react";

import WindowView from "@/components/WindowView";
import { getWindow, loadDemo, neighbors, showcaseId } from "@/lib/data";

/** /window opens on the showcase window (a Kelmarsh alarm with every number verified). */
export default function WindowIndexPage() {
  const id = showcaseId();
  const w = getWindow(id)!;
  const { prev, next } = neighbors(id);
  return (
    <Suspense fallback={null}>
      <WindowView w={w} meta={loadDemo().meta.channels} prev={prev} next={next} />
    </Suspense>
  );
}
