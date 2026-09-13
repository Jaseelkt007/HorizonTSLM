"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import { TurbineInfo, Timeframe } from "../lib/types";
import { useStream } from "../context/StreamContext";
import { generateTelemetrySeries } from "../lib/mock-data";
import {
  Sparkles,
  Send,
  CheckCircle2,
  AlertOctagon,
  Wrench,
  ShieldAlert,
  Bot,
  User,
  Activity,
  Wind,
  Gauge,
  Thermometer,
  RotateCcw,
  Zap,
  Clock,
  ArrowRight,
} from "lucide-react";

interface ModelDiagnosticBoxProps {
  turbine: TurbineInfo;
}

interface TelemetrySummaryData {
  timeframe: Timeframe;
  turbineId: string;
  turbineName: string;
  pointsCount: number;
  avgPower: number;
  latestPower: number;
  ratedPower: number;
  windLatest: number;
  windMin: number;
  windMax: number;
  bearingTemp: number;
  bearingExpected: number;
  gearboxTemp: number;
  generatorTemp: number;
  vibration: number;
  vibrationExpected: number;
  status: string;
  anomalyConfidence: number;
  sigmaDivergence: number;
  isAnomaly: boolean;
}

interface ModelAnswerData {
  finding: string;
  subsystem: string;
  predictedTTF: string | null;
  confidence: number;
  divergence: number;
  narrative: string;
  actionRecommendation: string;
  evidenceBadges: Array<{ label: string; value: string; color?: string }>;
  showActions?: boolean;
}

interface ChatMessage {
  id: string;
  role: "assistant" | "user";
  type: "telemetry_summary" | "model_answer" | "user_question" | "text";
  timestamp: string;
  content?: string;
  summaryData?: TelemetrySummaryData;
  modelAnswer?: ModelAnswerData;
}

export function ModelDiagnosticBox({ turbine }: ModelDiagnosticBoxProps) {
  const { timeframe, derateTurbine } = useStream();
  const [hasDerated, setHasDerated] = useState<boolean>(false);
  const [scheduledInspection, setScheduledInspection] = useState<boolean>(false);

  // Default pre-filled question for the operator asking about upcoming faults
  const defaultPrompt = useMemo(() => {
    return `What upcoming fault is anticipated on turbine ${turbine.id}, and what is the root cause?`;
  }, [turbine.id]);

  const [inputText, setInputText] = useState<string>(defaultPrompt);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Compute telemetry summary for the current turbine and selected timeframe
  const computeSummary = useMemo((): TelemetrySummaryData => {
    const points = generateTelemetrySeries(turbine.id, timeframe);
    const n = points.length || 1;
    const avgPower = Math.round(
      points.reduce((sum, p) => sum + (p.activePower || 0), 0) / n
    );
    const windSpeeds = points.map((p) => p.windSpeed || 0);
    const windMin = Math.min(...windSpeeds);
    const windMax = Math.max(...windSpeeds);
    const latest = points[points.length - 1] || {
      activePower: turbine.activePower,
      windSpeed: turbine.windSpeed,
      bearingTemp: turbine.bearingTemp,
      bearingTempExpected: turbine.bearingTemp - 3.2,
      gearboxTemp: turbine.gearboxTemp,
      generatorTemp: turbine.generatorTemp,
      vibrationIndex: turbine.vibrationIndex,
      vibrationExpected: 0.12,
    };

    const isAnomaly = turbine.status !== "normal" || points.some((p) => p.isAnomaly);

    return {
      timeframe,
      turbineId: turbine.id,
      turbineName: turbine.name,
      pointsCount: n,
      avgPower,
      latestPower: latest.activePower,
      ratedPower: turbine.ratedPower,
      windLatest: latest.windSpeed,
      windMin: parseFloat(windMin.toFixed(1)),
      windMax: parseFloat(windMax.toFixed(1)),
      bearingTemp: latest.bearingTemp,
      bearingExpected: latest.bearingTempExpected,
      gearboxTemp: latest.gearboxTemp,
      generatorTemp: latest.generatorTemp,
      vibration: latest.vibrationIndex,
      vibrationExpected: latest.vibrationExpected,
      status: turbine.status,
      anomalyConfidence: turbine.anomalyConfidence,
      sigmaDivergence: turbine.sigmaDivergence,
      isAnomaly,
    };
  }, [turbine, timeframe]);

  // Reset or initialize chat with telemetry summary when turbine or timeframe changes
  useEffect(() => {
    const initialSummaryMessage: ChatMessage = {
      id: `summary-${turbine.id}-${timeframe}`,
      role: "assistant",
      type: "telemetry_summary",
      timestamp: "Live Telemetry",
      summaryData: computeSummary,
    };

    setMessages([initialSummaryMessage]);
    setInputText(`What upcoming fault is anticipated on turbine ${turbine.id}, and what is the root cause?`);
    setHasDerated(false);
    setScheduledInspection(false);
  }, [turbine.id, timeframe, computeSummary]);

  // Auto-scroll chat to latest message
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isProcessing]);

  const handleDerate = () => {
    derateTurbine(turbine.id, 60);
    setHasDerated(true);
  };

  const handleSchedule = () => {
    setScheduledInspection(true);
  };

  const handleSendMessage = (textToSend?: string) => {
    const query = (textToSend !== undefined ? textToSend : inputText).trim();
    if (!query || isProcessing) return;

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      type: "user_question",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      content: query,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText("");
    setIsProcessing(true);

    // Simulate realistic foundation model inference over the multi-channel window
    setTimeout(() => {
      const isFaultTurbine = turbine.status !== "normal";
      const cleanSummary = turbine.diagnosticSummary
        ? turbine.diagnosticSummary.split("Answer:")[0].trim()
        : "";

      let answerFinding = "";
      let narrative = "";
      let subsystemName = turbine.faultSubsystem?.replace("_", " ") || "Nominal Drive Train";

      if (isFaultTurbine) {
        answerFinding = turbine.activeFault
          ? `Precursor Anomaly Detected: ${turbine.activeFault}`
          : "Elevated Thermal & Aerodynamic Asymmetry";
        narrative =
          cleanSummary ||
          `OpenTSLM analysis of the 144-step ${timeframe} SCADA window confirms statistical thermal runaway (${turbine.sigmaDivergence}σ divergence) and spectral vibration acceleration preceding forced shutdown.`;
      } else {
        answerFinding = "No Upcoming Faults Anticipated (Nominal IEC Envelope)";
        subsystemName = "Nominal (All Subsystems)";
        narrative = `Over the selected ${timeframe} SCADA window, all 19 physical telemetry channels remain strictly bounded within 1.0σ baseline variance. Aerodynamic power coefficient, bearing thermal gradients, and spectral acceleration match theoretical MM92 physics curves with zero degradation signatures.`;
      }

      const evidenceBadges = isFaultTurbine
        ? [
            { label: "Subsystem", value: subsystemName, color: "text-rose-400" },
            { label: "Thermal Drift", value: `${turbine.sigmaDivergence}σ`, color: "text-amber-400" },
            { label: "Lead Time (TTF)", value: turbine.predictedTTF ? `${turbine.predictedTTF} to trip` : "48h", color: "text-rose-400" },
            { label: "Ground Truth Verified", value: "86% Facts Verified", color: "text-emerald-400" },
          ]
        : [
            { label: "Subsystem", value: "Nominal", color: "text-emerald-400" },
            { label: "Thermal Drift", value: "0.2σ (Nominal)", color: "text-slate-300" },
            { label: "Lead Time", value: "No Trip Anticipated", color: "text-emerald-400" },
            { label: "Reliability Index", value: "99.4% Availability", color: "text-emerald-400" },
          ];

      const modelReply: ChatMessage = {
        id: `model-${Date.now()}`,
        role: "assistant",
        type: "model_answer",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        modelAnswer: {
          finding: answerFinding,
          subsystem: subsystemName,
          predictedTTF: turbine.predictedTTF,
          confidence: turbine.anomalyConfidence,
          divergence: turbine.sigmaDivergence,
          narrative,
          actionRecommendation: turbine.actionRecommendation,
          evidenceBadges,
          showActions: isFaultTurbine,
        },
      };

      setMessages((prev) => [...prev, modelReply]);
      setIsProcessing(false);
    }, 750);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const resetToSummary = () => {
    const initialSummaryMessage: ChatMessage = {
      id: `summary-${turbine.id}-${timeframe}`,
      role: "assistant",
      type: "telemetry_summary",
      timestamp: "Live Telemetry",
      summaryData: computeSummary,
    };
    setMessages([initialSummaryMessage]);
    setInputText(`What upcoming fault is anticipated on turbine ${turbine.id}, and what is the root cause?`);
  };

  return (
    <div className="minimal-card p-5 flex flex-col justify-between">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-3.5 border-b border-white/[0.06] mb-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-sky-400 flex items-center justify-center text-white shadow-md shadow-blue-500/20">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold text-white tracking-tight">
                Diagnostic Assistant
              </h3>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-400 font-semibold border border-blue-500/20">
                OpenTSLM v1.4
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Multi-channel SCADA foundation model inference & fault explainer
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={resetToSummary}
            title="Reset assistant chat"
            className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-slate-200 transition-all text-xs flex items-center gap-1"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-[11px]">Reset</span>
          </button>

          <span
            className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
              turbine.anomalyConfidence > 90
                ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                : turbine.anomalyConfidence > 75
                ? "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
            }`}
          >
            {turbine.anomalyConfidence}% Model Confidence
          </span>
        </div>
      </div>

      {/* Chat Messages Stream Area */}
      <div className="space-y-4 overflow-y-auto max-h-[380px] min-h-[260px] pr-1 mb-4 text-xs">
        {messages.map((msg) => {
          if (msg.role === "assistant" && msg.type === "telemetry_summary" && msg.summaryData) {
            const s = msg.summaryData;
            const isWarn = s.status !== "normal";

            return (
              <div key={msg.id} className="space-y-2 animate-fade-in">
                {/* Assistant header banner */}
                <div className="flex items-center gap-2 text-slate-400 text-[11px] font-medium">
                  <Bot className="w-3.5 h-3.5 text-sky-400" />
                  <span>Diagnostic Assistant</span>
                  <span className="text-slate-400">·</span>
                  <span className="text-slate-400">Default Telemetry Summary ({s.timeframe})</span>
                </div>

                {/* Structured Summary Card */}
                <div className="p-4 rounded-2xl bg-[#10131c] border border-white/[0.05] space-y-3 shadow-inner">
                  <div className="flex items-center justify-between gap-2 pb-2 border-b border-white/[0.04]">
                    <div className="flex items-center gap-2">
                      <Activity className="w-4 h-4 text-blue-400" />
                      <span className="text-white font-semibold text-xs">
                        {s.turbineName} ({s.turbineId}) Telemetry State
                      </span>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${
                        isWarn
                          ? "bg-rose-500/15 text-rose-400 border border-rose-500/25"
                          : "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25"
                      }`}
                    >
                      {isWarn ? "Anomaly Precursor Flagged" : "Nominal Window"}
                    </span>
                  </div>

                  {/* Quantitative Telemetry Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                    {/* Power Channel */}
                    <div className="p-2 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-0.5">
                      <div className="text-slate-400 flex items-center gap-1">
                        <Zap className="w-3 h-3 text-sky-400" />
                        <span>Active Power</span>
                      </div>
                      <div className="text-white font-bold text-xs">
                        {s.latestPower.toLocaleString()} kW
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Avg: {s.avgPower} kW / {s.ratedPower} kW
                      </div>
                    </div>

                    {/* Wind Channel */}
                    <div className="p-2 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-0.5">
                      <div className="text-slate-400 flex items-center gap-1">
                        <Wind className="w-3 h-3 text-emerald-400" />
                        <span>Wind Velocity</span>
                      </div>
                      <div className="text-white font-bold text-xs">
                        {s.windLatest} m/s
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Range: {s.windMin} – {s.windMax} m/s
                      </div>
                    </div>

                    {/* Bearing Temp */}
                    <div className="p-2 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-0.5">
                      <div className="text-slate-400 flex items-center gap-1">
                        <Thermometer className="w-3 h-3 text-rose-400" />
                        <span>Bearing Temp</span>
                      </div>
                      <div className={`font-bold text-xs ${isWarn ? "text-rose-400" : "text-white"}`}>
                        {s.bearingTemp} °C
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Normal: {s.bearingExpected} °C ({s.sigmaDivergence}σ)
                      </div>
                    </div>

                    {/* Vibration / Rotor */}
                    <div className="p-2 rounded-xl bg-white/[0.02] border border-white/[0.04] space-y-0.5">
                      <div className="text-slate-400 flex items-center gap-1">
                        <Gauge className="w-3 h-3 text-purple-400" />
                        <span>Vibration (g)</span>
                      </div>
                      <div className={`font-bold text-xs ${s.vibration > 0.3 ? "text-amber-400" : "text-white"}`}>
                        {s.vibration} g
                      </div>
                      <div className="text-[10px] text-slate-400">
                        Baseline: {s.vibrationExpected} g
                      </div>
                    </div>
                  </div>

                  {/* Summary Narrative Statement */}
                  <p className="text-slate-300 leading-relaxed font-normal text-xs pt-1">
                    {isWarn ? (
                      <>
                        <strong className="text-rose-400 font-semibold">Telemetry Alert: </strong>
                        During the current {s.timeframe} window, thermal gradient anomalies and vibration indices show significant divergence from normal operating envelopes. The pre-filled diagnostic inquiry below is ready to run deep foundation model inference on upcoming faults.
                      </>
                    ) : (
                      <>
                        <strong className="text-emerald-400 font-semibold">Nominal Baseline: </strong>
                        Sensor telemetry over the past {s.timeframe} shows standard power generation aligned with incoming wind vectors. You may ask the diagnostic assistant to anticipate any latent degradation or upcoming faults below.
                      </>
                    )}
                  </p>
                </div>
              </div>
            );
          }

          if (msg.role === "user") {
            return (
              <div key={msg.id} className="flex justify-end animate-fade-in">
                <div className="max-w-[85%] space-y-1">
                  <div className="flex items-center justify-end gap-1.5 text-slate-400 text-[11px]">
                    <span>Operator</span>
                    <User className="w-3 h-3 text-blue-400" />
                    <span className="text-slate-400 text-[10px]">{msg.timestamp}</span>
                  </div>
                  <div className="p-3.5 rounded-2xl bg-blue-600 text-white shadow-md shadow-blue-600/15 leading-relaxed font-medium">
                    {msg.content}
                  </div>
                </div>
              </div>
            );
          }

          if (msg.role === "assistant" && msg.type === "model_answer" && msg.modelAnswer) {
            const ans = msg.modelAnswer;

            return (
              <div key={msg.id} className="space-y-2 animate-fade-in">
                <div className="flex items-center gap-2 text-slate-400 text-[11px] font-medium">
                  <Bot className="w-3.5 h-3.5 text-sky-400" />
                  <span>OpenTSLM Model Diagnostic Response</span>
                  <span className="text-slate-400">·</span>
                  <span className="text-slate-400">{msg.timestamp}</span>
                </div>

                <div className="p-4 rounded-2xl bg-[#10131c] border border-blue-500/20 space-y-3.5 shadow-lg shadow-blue-500/5">
                  {/* Diagnosis Heading */}
                  <div className="flex items-start justify-between gap-3 pb-2.5 border-b border-white/[0.06]">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold">
                        Model Prognosis
                      </div>
                      <div className="text-sm font-bold text-white mt-0.5 flex items-center gap-2">
                        {ans.showActions ? (
                          <ShieldAlert className="w-4 h-4 text-rose-400 flex-shrink-0" />
                        ) : (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                        )}
                        <span>{ans.finding}</span>
                      </div>
                    </div>

                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30 flex-shrink-0">
                      Subsystem: {ans.subsystem}
                    </span>
                  </div>

                  {/* Narrative Body */}
                  <div className="text-xs text-slate-200 leading-relaxed font-normal bg-black/20 p-3 rounded-xl border border-white/[0.03]">
                    &ldquo;{ans.narrative}&rdquo;
                  </div>

                  {/* Multi-Channel Evidence Badges */}
                  <div className="flex flex-wrap gap-2 pt-0.5 text-[11px]">
                    {ans.evidenceBadges.map((badge, idx) => (
                      <span
                        key={idx}
                        className="px-2.5 py-1 rounded-full bg-white/[0.04] border border-white/[0.06] text-slate-300"
                      >
                        {badge.label}: <strong className={badge.color || "text-white"}>{badge.value}</strong>
                      </span>
                    ))}
                  </div>

                  {/* Recommended Action & Trigger Buttons */}
                  <div className="pt-3 border-t border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="text-xs text-slate-300">
                      <span className="text-slate-400 block text-[11px]">Recommended Action:</span>
                      {ans.actionRecommendation}
                    </div>

                    {ans.showActions && (
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                          onClick={handleDerate}
                          disabled={hasDerated}
                          className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
                            hasDerated
                              ? "bg-emerald-600/20 text-emerald-400 border border-emerald-500/30 cursor-default"
                              : "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-600/20 cursor-pointer"
                          }`}
                        >
                          {hasDerated ? (
                            <>
                              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                              <span>Derate Applied (60%)</span>
                            </>
                          ) : (
                            <>
                              <AlertOctagon className="w-3.5 h-3.5" />
                              <span>Derate Output to 60%</span>
                            </>
                          )}
                        </button>

                        <button
                          onClick={handleSchedule}
                          disabled={scheduledInspection}
                          className={`px-3 py-1.5 rounded-xl text-xs font-medium border border-white/[0.08] transition-all flex items-center gap-1.5 ${
                            scheduledInspection
                              ? "bg-white/[0.08] text-white cursor-default"
                              : "bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 cursor-pointer"
                          }`}
                        >
                          <Wrench className="w-3.5 h-3.5 text-slate-400" />
                          <span>{scheduledInspection ? "Dispatched" : "Schedule Inspection"}</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          }

          return null;
        })}

        {/* Inference Processing Indicator */}
        {isProcessing && (
          <div className="space-y-1.5 animate-pulse">
            <div className="flex items-center gap-2 text-slate-400 text-[11px] font-medium">
              <Bot className="w-3.5 h-3.5 text-sky-400 animate-spin" />
              <span>OpenTSLM Diagnostic Engine</span>
            </div>
            <div className="p-4 rounded-2xl bg-[#10131c] border border-blue-500/30 space-y-2">
              <div className="flex items-center gap-2 text-xs text-sky-400 font-medium">
                <Sparkles className="w-4 h-4 animate-bounce" />
                <span>Processing 144-step multi-channel telemetry with OpenTSLM...</span>
              </div>
              <p className="text-[11px] text-slate-400">
                Correlating thermal divergence, rotor torque, and vibration kurtosis against Zenodo ground-truth models...
              </p>
              <div className="w-full bg-white/[0.06] rounded-full h-1 overflow-hidden">
                <div className="bg-gradient-to-r from-blue-500 to-sky-300 h-full w-2/3 animate-pulse rounded-full" />
              </div>
            </div>
          </div>
        )}

        <div ref={chatBottomRef} />
      </div>

      {/* Suggested Quick Question Chips */}
      <div className="pt-2 border-t border-white/[0.04] mb-2 flex items-center gap-1.5 overflow-x-auto text-[11px]">
        <span className="text-slate-400 text-[10px] uppercase font-semibold mr-1 flex-shrink-0">
          Suggested:
        </span>
        {[
          { label: "Upcoming Fault & Root Cause", query: `What upcoming fault is anticipated on turbine ${turbine.id}, and what is the root cause?` },
          { label: "Telemetry Evidence", query: `What specific sensor anomalies support this prediction on turbine ${turbine.id}?` },
          { label: "Corrective Actions", query: `What immediate operational derate or maintenance is required for ${turbine.id}?` },
        ].map((chip, idx) => (
          <button
            key={idx}
            onClick={() => {
              setInputText(chip.query);
              handleSendMessage(chip.query);
            }}
            className="px-2.5 py-1 rounded-lg bg-white/[0.03] hover:bg-white/[0.07] border border-white/[0.05] text-slate-300 hover:text-white transition-all whitespace-nowrap flex-shrink-0"
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Chat Input Bar with Pre-filled Question */}
      <div className="relative flex items-center gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask about faults on ${turbine.id}...`}
            disabled={isProcessing}
            className="w-full bg-[#10131c] border border-white/[0.08] focus:border-blue-500/50 rounded-xl px-3.5 py-2.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500/40 transition-all pr-10"
          />
        </div>

        <button
          onClick={() => handleSendMessage()}
          disabled={!inputText.trim() || isProcessing}
          className={`p-2.5 rounded-xl font-medium transition-all flex items-center justify-center flex-shrink-0 ${
            inputText.trim() && !isProcessing
              ? "bg-blue-600 hover:bg-blue-500 text-white shadow-md shadow-blue-500/25 cursor-pointer"
              : "bg-white/[0.05] text-slate-400 cursor-not-allowed"
          }`}
          title="Send query to OpenTSLM"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
