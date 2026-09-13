"use client";

import { useEffect, useState } from "react";

export type Claim = { start: number; end: number; ok: boolean };
export type SavedSeries = { name: string; label: string; unit: string; values: number[] };
export type SavedWindow = {
  id: string; farm: string; turbine: number; anchor: string; horizon_h: number; state: string; model: string;
  prePrompt: string; channels: { text: string; n: number }[]; postPrompt: string;
  text: string; claims: Claim[]; pred: string; gold: string; score: number;
  outcome: { message: string | null; lead_time_min: number | null; duration_h: number | null };
  series: SavedSeries[];
};

const cache = new Map<string, Promise<SavedWindow | null>>();

/** The saved held-out window behind a turbine card (see /api/window): fetched once per window id, shared by every card. */
export function useSavedWindow(id: string | undefined): SavedWindow | null | undefined {
  const [w, setW] = useState<SavedWindow | null | undefined>(undefined);
  useEffect(() => {
    if (!id) { setW(null); return; }
    let cancelled = false;
    setW(undefined);
    if (!cache.has(id)) cache.set(id, fetch(`/api/window?id=${encodeURIComponent(id)}`).then((r) => (r.ok ? r.json() : null)).catch(() => null));
    cache.get(id)!.then((v) => { if (!cancelled) setW(v); });
    return () => { cancelled = true; };
  }, [id]);
  return w;
}
