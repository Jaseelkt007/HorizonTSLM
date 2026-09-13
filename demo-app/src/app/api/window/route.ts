import { NextRequest, NextResponse } from "next/server";
import demoData from "../../../data/demo_data.json";

/**
 * A saved held-out window with the exact prompt the model received and the answer it generated
 * (src/data/demo_data.json, written by scripts/build_demo_data.py from the run's predictions).
 * The prompt is rebuilt with the same template and window statistics as the training code
 * (src/turbine_tslm/data/prompts.py, training/turbine_dataset.py): nothing here is invented.
 */

type Claim = { start: number; end: number; ok: boolean };
type WindowRecord = {
  id: string; farm: string; turbine: number; anchor: string; horizon_h: number; state: string;
  gold: string; pred: string; score: number; text: string; claims: Claim[];
  outcome: { message: string | null; lead_time_min: number | null; duration_h: number | null };
  channels: Record<string, number[]>;
};
type ChannelMeta = { name: string; label: string; unit: string };
const DATA = demoData as unknown as { meta: { channels: ChannelMeta[]; model: string }; windows: WindowRecord[] };

const FAULT_CLASSES = ["generator_cooling", "brake_hydraulics", "pitch_system", "converter_grid", "gearbox_lubrication", "yaw_cable", "structural_overspeed", "sensor_comms"];
const TURBINE_TYPE: Record<string, string> = { penmanshiel: "Senvion MM82", kelmarsh: "Senvion MM92" };
const RATED_KW = 2050;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const mean = (a: number[]) => a.reduce((s, v) => s + v, 0) / a.length;
const std = (a: number[]) => { const m = mean(a); return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / a.length); };

function prePrompt(w: WindowRecord): string {
  const turbineId = `${w.farm}-${String(w.turbine).padStart(2, "0")}`;
  const month = MONTHS[Number(w.anchor.slice(5, 7)) - 1];
  return `You are monitoring wind turbine ${turbineId} (${TURBINE_TYPE[w.farm]}, ${RATED_KW} kW) in ${month}. ` +
    `Below are the last 24 hours of 10-minute SCADA signals, ending now. The turbine is currently ${w.state}. ` +
    `Analyse the signals and decide whether a fault-related stop (forced outage) is likely to begin within the next ${w.horizon_h} hours. ` +
    `If yes, name the subsystem from: ${FAULT_CLASSES.join(", ")}. Do not state a decision until the final line. End with "Answer: ".`;
}

/** series_text(..., rich): mean, std, first 6 h, the hour ending 6 h before the end, last hour — all inside the window. */
function channelLines(w: WindowRecord): { text: string; n: number }[] {
  return DATA.meta.channels.map((c) => {
    const v = w.channels[c.name];
    const n = v.length;
    const f6 = mean(v.slice(0, Math.floor(n / 4)));
    const a6 = mean(v.slice(n - 42, n - 36));
    const l1 = mean(v.slice(n - 6));
    return { text: `${c.label} in ${c.unit}, 10-minute means over 24 h, mean ${mean(v).toFixed(1)} std ${std(v).toFixed(1)}, first 6 h ${f6.toFixed(1)}, 6 h before the end ${a6.toFixed(1)}, last hour ${l1.toFixed(1)}:`, n };
  });
}

export async function GET(request: NextRequest) {
  const id = request.nextUrl.searchParams.get("id") ?? "";
  const w = DATA.windows.find((x) => x.id === id);
  if (!w) return NextResponse.json({ error: `No saved window ${id}` }, { status: 404 });
  return NextResponse.json({
    id: w.id, farm: w.farm, turbine: w.turbine, anchor: w.anchor, horizon_h: w.horizon_h, state: w.state,
    model: DATA.meta.model,
    prePrompt: prePrompt(w), channels: channelLines(w), postPrompt: "Assessment:",
    text: w.text, claims: w.claims, pred: w.pred, gold: w.gold, score: w.score, outcome: w.outcome,
  });
}
