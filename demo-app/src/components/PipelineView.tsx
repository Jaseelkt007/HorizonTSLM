"use client";

import React from "react";

/**
 * The end-to-end pipeline console (repo folder `replay/`, copied to `public/pipeline/`): pick a held-out
 * Kelmarsh window, watch the 24 h of SCADA go through OpenTSLM-Flamingo, read the answer with every number
 * checked against the window and against the alarm log. Self-contained static page, so it is embedded as-is.
 */
export function PipelineView() {
  return (
    <div className="h-[calc(100vh-4rem)] min-h-[640px] w-full bg-[#0f141b]">
      <iframe
        title="TSLM pipeline explainer"
        src="/pipeline/index.html?embed&theme=dark"
        className="w-full h-full border-0 block"
        allow="fullscreen"
      />
    </div>
  );
}
