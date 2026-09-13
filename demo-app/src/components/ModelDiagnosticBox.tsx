"use client";

import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bot, Send, User } from "lucide-react";
import { TurbineInfo } from "../lib/types";
import { useStream } from "../context/StreamContext";
import { generateTelemetrySeries } from "../lib/mock-data";

type ChatMessage = { id: string; role: "assistant" | "user"; content: string };

function telemetrySummary(turbine: TurbineInfo, timeframe: "24h" | "7d" | "30d") {
  const points = generateTelemetrySeries(turbine.id, timeframe, turbine.farm);
  const latest = points.at(-1);
  const averagePower = points.length
    ? Math.round(points.reduce((sum, point) => sum + point.activePower, 0) / points.length)
    : turbine.activePower;
  const wind = latest?.windSpeed ?? turbine.windSpeed;
  const bearing = latest?.bearingTemp ?? turbine.bearingTemp;
  const gearbox = latest?.gearboxTemp ?? turbine.gearboxTemp;
  const generator = latest?.generatorTemp ?? turbine.generatorTemp;
  return `Current ${timeframe} SCADA summary for ${turbine.name}: ${points.length} 10-minute observations; average power ${averagePower.toLocaleString()} kW (latest ${(latest?.activePower ?? turbine.activePower).toLocaleString()} kW) at ${wind.toFixed(1)} m/s wind. Latest temperatures: main bearing ${bearing.toFixed(1)} °C, gearbox oil ${gearbox.toFixed(1)} °C, generator ${generator.toFixed(1)} °C. This briefing is calculated from the selected timeframe; no model has been loaded.`;
}

/** A chat interface whose first model load happens only when an operator sends a question. */
export function ModelDiagnosticBox({ turbine }: { turbine: TurbineInfo }) {
  const { timeframe } = useStream();
  const question = useMemo(() => `What upcoming fault is anticipated on turbine ${turbine.id}, and what is the root cause?`, [turbine.id]);
  const summary = useMemo(() => telemetrySummary(turbine, timeframe), [turbine, timeframe]);
  const [input, setInput] = useState(question);
  const [messages, setMessages] = useState<ChatMessage[]>([{ id: "summary", role: "assistant", content: summary }]);
  const [isProcessing, setIsProcessing] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([{ id: `summary-${turbine.farm}-${turbine.id}-${timeframe}`, role: "assistant", content: summary }]);
    setInput(question);
  }, [question, summary, timeframe, turbine.farm, turbine.id]);
  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages, isProcessing]);

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

  return (
    <section className="minimal-card p-5" aria-label="Diagnostic assistant">
      <div className="mb-4"><h3 className="text-base font-bold text-white">Diagnostic Assistant</h3><p className="mt-0.5 text-xs text-slate-400">OpenTSLM · selected window {turbine.sourceWindowId}</p></div>
      <div className="mb-4 max-h-[360px] min-h-[190px] space-y-3 overflow-y-auto pr-1 text-xs">
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
