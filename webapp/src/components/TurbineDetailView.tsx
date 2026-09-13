"use client";

import Link from "next/link";
import { useState } from "react";

import { cls, stateLabel, tcode, tname } from "@/lib/format";

import { computeImpact, fmtGbp } from "@/lib/impact";
import { CHANNEL_SHORT, FARM, SERIES } from "@/lib/labels";
import { fmtDateTime, parseAnchor } from "@/lib/time";
import type { ChannelMeta, Farm, WindowRecord, WindowSummary } from "@/lib/types";

import ChannelList from "./ChannelList";
import SensorCopilot from "./SensorCopilot";
import SignalPanels from "./SignalPanels";
import TurbineBenchmark from "./TurbineBenchmark";

interface Props {
  turbine: number;
  farm: Farm;
  meta: ChannelMeta[];
  currentRecord: WindowRecord;
  turbineRecords: WindowRecord[];
  farmWindows: WindowSummary[];
  prevTurbine?: number;
  nextTurbine?: number;
}

const SUBSYSTEM_GROUPS = [
  {
    id: "thermal",
    label: "Drivetrain Thermal",
    channels: [
      "gen_bearing_rear_temperature",
      "gen_bearing_front_temperature",
      "stator_temperature",
      "gear_oil_temperature",
      "main_bearing_temperature",
    ],
  },
  {
    id: "structural",
    label: "Dynamics & Vibration",
    channels: ["tower_acceleration_x", "rotor_speed", "power_curve_residual"],
  },
  {
    id: "hydraulics",
    label: "Hydraulics & Lubrication",
    channels: ["gear_oil_inlet_pressure", "ambient_temperature"],
  },
  {
    id: "electrical",
    label: "Electrical & Grid",
    channels: ["power", "reactive_power", "grid_voltage", "grid_frequency"],
  },
  {
    id: "aerodynamics",
    label: "Aerodynamics & Pitch",
    channels: ["wind_speed", "wind_direction", "pitch_angle", "nacelle_position"],
  },
];

export default function TurbineDetailView({
  turbine,
  farm,
  meta,
  currentRecord,
  turbineRecords,
  farmWindows,
  prevTurbine,
  nextTurbine,
}: Props) {
  const [activeGroup, setActiveGroup] = useState<string>("thermal");
  const [rightTab, setRightTab] = useState<"telemetry" | "benchmark" | "channels">("telemetry");
  const [pinned, setPinned] = useState<string[]>([
    "power",
    "gen_bearing_rear_temperature",
    "tower_acceleration_x",
  ]);

  const impact = computeImpact(currentRecord);
  const w = currentRecord;
  const isTripPredicted = w.pred !== "none" || w.score >= 0.5;
  const event = isTripPredicted
    ? { leadMin: (w.horizon_h || 3) * 60, message: `Precursor Risk Horizon: +${w.horizon_h || 3}h (${cls(w.pred)})` }
    : null;


  const series = pinned.map((name, k) => {
    const m = meta.find((c) => c.name === name)!;
    return {
      name,
      label: CHANNEL_SHORT[name] ?? m?.label ?? name,
      unit: m?.unit ?? "",
      values: w.channels[name] || [],
      color: SERIES[k % SERIES.length],
    };
  });

  const toggle = (name: string) => {
    setPinned((p) =>
      p.includes(name)
        ? p.length > 1
          ? p.filter((x) => x !== name)
          : p
        : p.length >= 3
          ? [...p.slice(1), name]
          : [...p, name],
    );
  };

  const selectGroupChannels = (groupId: string) => {
    setActiveGroup(groupId);
    const grp = SUBSYSTEM_GROUPS.find((g) => g.id === groupId);
    if (grp && grp.channels.length > 0) {
      setPinned(grp.channels.slice(0, 3));
    }
  };

  return (
    <div className="page" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* 1. Sleek Minimalist Header */}
      <div className="pagehead" style={{ paddingBlock: "12px 0", marginBottom: 0 }}>
        <div>
          <div className="crumbs" style={{ marginBottom: 4 }}>
            <Link href="/">← Wind Farm Overview</Link>
            <span>/</span>
            <span>{FARM[farm].name}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600 }}>
              {tname({ farm, turbine })}
            </h1>
            <span
              className="chip"
              style={{
                background:
                  impact.urgency === "critical"
                    ? "rgba(239, 68, 68, 0.12)"
                    : impact.urgency === "advisory"
                      ? "rgba(245, 158, 11, 0.12)"
                      : "rgba(16, 185, 129, 0.12)",
                color:
                  impact.urgency === "critical"
                    ? "#dc2626"
                    : impact.urgency === "advisory"
                      ? "#d97706"
                      : "#059669",
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              ● {impact.urgency.toUpperCase()}
            </span>
          </div>
          <p className="sub" style={{ margin: "4px 0 0", fontSize: 13 }}>
            {FARM[farm].type} · 2.05 MW Nameplate · {stateLabel(w.state)} · Window ending {fmtDateTime(parseAnchor(w.anchor))}
          </p>
        </div>

        {/* Minimalist Inline Vitals & Navigation */}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span className="chip neutral">
            ⚡ {typeof w.facts?.power_last1h === "number" ? `${Math.round(w.facts.power_last1h)} kW Active` : "Nominal Active"}
          </span>

          <span className="chip neutral">
            📈 {impact.energeticAvailabilityPct}% Availability
          </span>
          {impact.totalFinancialRiskGbp > 0 && (
            <span
              className="chip"
              style={{ background: "rgba(239, 68, 68, 0.08)", color: "#dc2626", fontWeight: 600 }}
            >
              ⚠️ {fmtGbp(impact.totalFinancialRiskGbp)} Risk
            </span>
          )}

          <div style={{ display: "inline-flex", gap: 4, marginLeft: 6 }}>
            {prevTurbine && (
              <Link className="btn sm" href={`/turbines/${farm}/${prevTurbine}`}>
                ← {tcode({ turbine: prevTurbine })}
              </Link>
            )}
            {nextTurbine && (
              <Link className="btn sm" href={`/turbines/${farm}/${nextTurbine}`}>
                {tcode({ turbine: nextTurbine })} →
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* 2. Side-by-Side Cockpit: AI Copilot (Left) & Telemetry / Benchmark Deck (Right) */}
      <div style={{ display: "grid", gridTemplateColumns: "1.08fr 0.92fr", gap: 16, alignItems: "start" }}>
        {/* Left Column: AI Sensor Copilot */}
        <SensorCopilot
          turbine={turbine}
          farm={farm}
          currentRecord={currentRecord}
          turbineRecords={turbineRecords}
        />

        {/* Right Column: Telemetry & Benchmark Cockpit */}
        <div className="card" style={{ padding: "16px", display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 10 }}>
            <div className="seg" role="group" aria-label="Turbine Diagnostics Tabs">
              <button
                type="button"
                aria-pressed={rightTab === "telemetry"}
                onClick={() => setRightTab("telemetry")}
              >
                Telemetry Signals
              </button>
              <button
                type="button"
                aria-pressed={rightTab === "benchmark"}
                onClick={() => setRightTab("benchmark")}
              >
                Fleet Benchmark
              </button>
              <button
                type="button"
                aria-pressed={rightTab === "channels"}
                onClick={() => setRightTab("channels")}
              >
                All 19 Channels
              </button>
            </div>
            <span className="hint" style={{ fontSize: 11.5 }}>
              {rightTab === "telemetry" && "10-Min SCADA Streams"}
              {rightTab === "benchmark" && "Peer Comparison Across Farm"}
              {rightTab === "channels" && "Raw SCADA Channel Inventory"}
            </span>
          </div>

          {rightTab === "telemetry" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {SUBSYSTEM_GROUPS.map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    className={`btn sm ${activeGroup === g.id ? "primary" : ""}`}
                    style={{ fontSize: 11.5, padding: "4px 8px" }}
                    onClick={() => selectGroupChannels(g.id)}
                  >
                    {g.label}
                  </button>
                ))}
              </div>

              <SignalPanels
                anchor={w.anchor}
                series={series}
                horizonH={w.horizon_h}
                event={event}
                panelHeight={110}
              />
            </div>
          )}

          {rightTab === "benchmark" && (
            <TurbineBenchmark
              currentTurbine={turbine}
              farmWindows={farmWindows}
              currentRecord={currentRecord}
            />
          )}

          {rightTab === "channels" && (
            <div style={{ maxHeight: 380, overflowY: "auto" }}>
              <ChannelList
                meta={meta}
                channels={w.channels}
                cited={new Set(["power", "gen_bearing_rear_temperature", "tower_acceleration_x"])}
                pinned={pinned}
                onToggle={toggle}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
