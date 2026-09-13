"use client";

import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Send, User } from "lucide-react";
import { TurbineInfo } from "../lib/types";

type ChatMessage = { id: string; role: "assistant" | "user"; content: string };
type Claim = { start: number; end: number; ok: boolean };
type SavedWindow = {
  id: string; anchor: string; horizon_h: number; state: string; model: string;
  prePrompt: string; channels: { text: string; n: number }[]; postPrompt: string;
  text: string; claims: Claim[]; pred: string; gold: string; score: number;
  outcome: { message: string | null; lead_time_min: number | null; duration_h: number | null };
};

const CLASS_LABEL: Record<string, string> = { generator_cooling: "generator cooling", gearbox_lubrication: "gearbox lubrication", pitch_system: "pitch system", structural_overspeed: "structural / overspeed", converter_grid: "converter / grid", brake_hydraulics: "brake / hydraulics", yaw_cable: "yaw / cable", sensor_comms: "sensor / comms", none: "no fault stop" };
const dur = (min: number) => { const h = Math.floor(min / 60), r = min % 60; return h ? `${h} h${r ? " " + String(r).padStart(2, "0") + " min" : ""}` : `${r} min`; };

/** The generated text with every numeric claim marked verified (dotted) or wrong (wavy) against the window. */
function MarkedText({ text, claims }: { text: string; claims: Claim[] }) {
  const cut = text.search(/Answer\s*:/i);
  const body = cut < 0 ? text : text.slice(0, cut).trimEnd();
  const answer = cut < 0 ? "" : text.slice(cut).trim();
  const parts: React.ReactNode[] = [];
  let pos = 0;
  for (const c of claims) {
    if (c.start < pos || c.end > body.length) continue;
    if (c.start > pos) parts.push(body.slice(pos, c.start));
    parts.push(<mark key={c.start} title={c.ok ? "verified against the window" : "does not match the window"} className={c.ok ? "bg-transparent text-inherit underline decoration-dotted decoration-emerald-400 decoration-[1.5px] underline-offset-[3px]" : "bg-transparent text-inherit underline decoration-wavy decoration-rose-400 decoration-[1.5px] underline-offset-[3px]"}>{body.slice(c.start, c.end)}</mark>);
    pos = c.end;
  }
  if (pos < body.length) parts.push(body.slice(pos));
  return <>
    <span>{parts}</span>
    {answer && <code className="mt-2 block w-fit rounded-lg border border-white/[0.08] bg-[#10131c] px-2 py-1 font-mono text-[11.5px] text-sky-300">{answer}</code>}
  </>;
}

/** A chat interface: the saved window's real prompt and the model's real answer first; the Send button
 *  runs live inference (needs the local model, see README). */
export function ModelDiagnosticBox({ turbine }: { turbine: TurbineInfo }) {
  const question = useMemo(() => `What upcoming fault is anticipated on turbine ${turbine.id}, and what is the root cause?`, [turbine.id]);
  const [input, setInput] = useState(question);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [saved, setSaved] = useState<SavedWindow | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setMessages([]); setSaved(null); setShowPrompt(false); setInput(question);
    fetch(`/api/window?id=${encodeURIComponent(turbine.sourceWindowId)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((w: SavedWindow | null) => { if (!cancelled) setSaved(w); })
      .catch(() => { if (!cancelled) setSaved(null); });
    return () => { cancelled = true; };
  }, [question, turbine.sourceWindowId]);
  useEffect(() => {
    // Block body on purpose: an arrow that returns scrollIntoView's result makes React treat it as a
    // cleanup function and crash the view ("u is not a function") in production.
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isProcessing) return;
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: "user", content: text }]);
    setInput("");
    setIsProcessing(true);
    try {
      const response = await fetch("/api/diagnose", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sourceWindowId: turbine.sourceWindowId, question: text }),
      });
      const result: { answer?: string; error?: string } = await response.json();
      if (!response.ok || !result.answer) throw new Error(result.error || "The diagnostic model returned no answer.");
      const answer = result.answer;
      setMessages((current) => [...current, { id: `assistant-${Date.now()}`, role: "assistant", content: answer }]);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "Unknown inference error";
      setMessages((current) => [...current, { id: `error-${Date.now()}`, role: "assistant", content: `Unable to run OpenTSLM: ${detail}` }]);
    } finally { setIsProcessing(false); }
  }

  const nOk = saved ? saved.claims.filter((c) => c.ok).length : 0;
  return (
    <section className="minimal-card p-5" aria-label="Diagnostic assistant">
      <div className="mb-4"><h3 className="text-base font-bold text-white">Diagnostic Assistant</h3><p className="mt-0.5 text-xs text-slate-400">OpenTSLM-Flamingo{saved ? ` · ${saved.model}` : ""} · saved window {turbine.sourceWindowId}{saved ? ` · 24 h ending ${saved.anchor} · asked ${saved.horizon_h} h ahead` : ""}</p></div>
      <div className="mb-4 max-h-[520px] min-h-[190px] space-y-3 overflow-y-auto pr-1 text-xs">
        {!saved && <p className="rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 text-slate-400">Loading the saved window…</p>}
        {saved && <>
          <div className="ml-auto max-w-[92%]">
            <div className="mb-1 flex items-center justify-end gap-1.5 text-[11px] text-slate-400"><span>Input prompt · exactly what the model receives</span><User className="h-3 w-3" /></div>
            <div className="whitespace-pre-wrap rounded-2xl bg-blue-600 p-3 leading-relaxed text-white">
              {saved.prePrompt}
              <div className="mt-2 border-t border-white/20 pt-2 text-[11px] text-blue-100">
                {(showPrompt ? saved.channels : saved.channels.slice(0, 2)).map((c, i) => <div key={i} className="mb-1"><span className="font-mono text-[10.5px] text-blue-200">⟨TS⟩</span> {c.text} <span className="font-mono text-[10.5px] text-blue-200">[{c.n} values → 36 patches] ⟨endofchunk⟩</span></div>)}
                {!showPrompt && <button type="button" onClick={() => setShowPrompt(true)} className="mt-1 underline decoration-dotted">… {saved.channels.length - 2} more channel descriptions — show the full prompt</button>}
                {showPrompt && <div className="mt-1">{saved.postPrompt}</div>}
              </div>
            </div>
          </div>
          <div className="max-w-[92%]">
            <div className="mb-1 flex items-center gap-1.5 text-[11px] text-slate-400"><Bot className="h-3.5 w-3.5 text-sky-400" /><span>Model answer · generated for this window</span></div>
            <div className="whitespace-pre-wrap rounded-2xl border border-white/[0.06] bg-white/[0.03] p-3 leading-relaxed text-slate-200">
              <MarkedText text={saved.text} claims={saved.claims} />
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-white/[0.06] pt-2 text-[11px] text-slate-400">
                <span><span className="text-slate-200">{nOk} of {saved.claims.length}</span> numbers verified against the window</span>
                <span>{saved.gold === "none" ? `Log: no fault stop in the next ${saved.horizon_h} h` : `Log: ${saved.outcome.message ?? CLASS_LABEL[saved.gold]}${saved.outcome.lead_time_min != null ? ` · ${dur(saved.outcome.lead_time_min)} after the window` : ""}`}</span>
                <span className={saved.pred === saved.gold ? "text-emerald-400" : "text-rose-400"}>{saved.pred === saved.gold ? "answer matches the log" : "answer does not match the log"}</span>
              </div>
            </div>
          </div>
        </>}
        {messages.map((message) => <div key={message.id} className={message.role === "user" ? "ml-auto max-w-[85%]" : "max-w-[92%]"}>
          <div className={`mb-1 flex items-center gap-1.5 text-[11px] text-slate-400 ${message.role === "user" ? "justify-end" : ""}`}>{message.role === "user" ? <><span>Operator</span><User className="h-3 w-3" /></> : <><Bot className="h-3.5 w-3.5 text-sky-400" /><span>Diagnostic Assistant</span></>}</div>
          <p className={`whitespace-pre-wrap rounded-2xl p-3 leading-relaxed ${message.role === "user" ? "bg-blue-600 text-white" : "border border-white/[0.06] bg-white/[0.03] text-slate-200"}`}>{message.content}</p>
        </div>)}
        {isProcessing && <div className="max-w-[92%]"><div className="mb-1 flex items-center gap-1.5 text-[11px] text-slate-400"><Bot className="h-3.5 w-3.5 animate-spin text-sky-400" />Diagnostic Assistant</div><p className="rounded-2xl border border-blue-400/25 bg-blue-400/5 p-3 text-slate-300">Loading OpenTSLM and evaluating the selected 24-hour SCADA window…</p></div>}
        <div ref={bottom} />
      </div>
      <form onSubmit={send} className="flex gap-2">
        <input aria-label="Diagnostic question" value={input} onChange={(event) => setInput(event.target.value)} disabled={isProcessing} className="min-w-0 flex-1 rounded-xl border border-white/[0.08] bg-[#10131c] px-3 py-2.5 text-xs text-white outline-none focus:border-blue-500/50 disabled:opacity-60" />
        <button type="submit" disabled={!input.trim() || isProcessing} className="rounded-xl bg-blue-600 p-2.5 text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40" title="Send to OpenTSLM"><Send className="h-4 w-4" /></button>
      </form>
    </section>
  );
}
