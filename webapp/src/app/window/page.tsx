import { Suspense } from "react";

import WindowDetail from "@/components/WindowDetail";
import { getWindow, loadDemo, showcaseId } from "@/lib/data";

/** /window opens on the showcase window (a Kelmarsh alarm with every number verified). */
export default function WindowIndexPage() {
  const w = getWindow(showcaseId())!;
  return (
    <Suspense fallback={null}>
      <WindowDetail w={w} meta={loadDemo().meta.channels} />
    </Suspense>
  );
}
