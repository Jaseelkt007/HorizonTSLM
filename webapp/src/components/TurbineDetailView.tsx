"use client";

import Link from "next/link";
import { useState } from "react";

import { cls, stateLabel, tcode, tname } from "@/lib/format";
import { computeImpact, fmtGbp, fmtMWh } from "@/lib/impact";
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
  const [pinned, setPinned] = useState<string[]>([
    "power",
    "gen_bearing_rear_temperature",
    "tower_acceleration_x",
  ]);

  const impact = computeImpact(currentRecord);
  const w = currentRecord;
  const o = w.outcome;
  const event =
    w.gold === "none" || o.lead_time_min == null
      ? null
      : { leadMin: o.lead_time_min, message: o.message ?? cls(w.gold) };

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
    <div className="page" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Top Header */}
      <div className="pagehead">
        <div>
          <div className="crumbs">
            <Link href="/">Command Center</Link>
            <span>/</span>
            <Link href={`/farms/${farm}/`}>{FARM[farm].name}</Link>
            <span>/</span>
            <span>{tcode({ turbine })}</span>
          </div>
          <h1 style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
            {tname({ farm, turbine })}
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
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {impact.urgency.toUpperCase()}
            </span>
          </h1>
          <p className="sub">
            {FARM[farm].type} · 2.05 MW Nameplate · {stateLabel(w.state)} · Window ending {fmtDateTime(parseAnchor(w.anchor))}
          </p>
        </div>

        <div className="actions">
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
          <Link className="btn sm" href="/">
            Overview Map
          </Link>
        </div>
      </div>

      {/* Turbine Executive Metrics Strip */}
      <div className="kpis">
        <div className="card kpi">
          <span className="l">Operating Active Power</span>
          <span className="v num">
            {typeof w.facts?.power_last1h === "number" ? Math.round(w.facts.power_last1h) : 2040} kW
          </span>
          <span className="c">Rated 2.05 MW capacity</span>
        </div>
        <div className="card kpi">
          <span className="l">Energetic Availability</span>
          <span className="v num">{impact.energeticAvailabilityPct} %</span>
          <span className="c">
            {impact.lostMWh > 0 ? `${fmtMWh(impact.lostMWh)} potential loss` : "Nominal yield"}
          </span>
        </div>
        <div className="card kpi">
          <span className="l">Financial Exposure at Risk</span>
          <span
            className="v num"
            style={{ color: impact.totalFinancialRiskGbp > 0 ? "#dc2626" : undefined }}
          >
            {impact.totalFinancialRiskGbp > 0 ? fmtGbp(impact.totalFinancialRiskGbp) : "£0"}
          </span>
          <span className="c">Generation loss + emergency O&M</span>
        </div>
        <div className="card kpi">
          <span className="l">Power Curve Residual</span>
          <span className="v num">
            {impact.powerCurveResidualKw >= 0
              ? `+${impact.powerCurveResidualKw}`
              : impact.powerCurveResidualKw}{" "}
            kW
          </span>
          <span className="c">Aerodynamic drag vs. farm model</span>
        </div>
      </div>

      {/* 1. SCADA Diagnostic Copilot & Pre-filled Model Inference */}
      <SensorCopilot
        turbine={turbine}
        farm={farm}
        currentRecord={currentRecord}
        turbineRecords={turbineRecords}
      />

      {/* 2. Detailed Multi-Channel Telemetry Workspace */}
      <div className="card" style={{ padding: "18px 20px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: 12,
            marginBottom: 14,
          }}
        >
          <div>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
              Detailed Sensor Telemetry (10-Minute SCADA Channels)
            </h3>
            <span className="hint">
              Synchronized 24-hour time series ending at anchor &ldquo;now&rdquo;. Nothing after anchor is seen by model.
            </span>
          </div>

          <div className="seg" role="group" aria-label="Subsystem Groups">
            {SUBSYSTEM_GROUPS.map((g) => (
              <button
                key={g.id}
                type="button"
                aria-pressed={activeGroup === g.id}
                onClick={() => selectGroupChannels(g.id)}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 240px", gap: 16 }}>
          <div style={{ padding: "8px 0" }}>
            <SignalPanels
              anchor={w.anchor}
              series={series}
              horizonH={w.horizon_h}
              event={event}
              panelHeight={120}
            />
          </div>

          <div style={{ borderLeft: "1px solid var(--line)", paddingLeft: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase", marginBottom: 8 }}>
              Click to Pin Channel (Max 3)
            </div>
            <ChannelList
              meta={meta}
              channels={w.channels}
              cited={new Set(["power", "gen_bearing_rear_temperature", "tower_acceleration_x"])}
              pinned={pinned}
              onToggle={toggle}
            />
          </div>
        </div>
      </div>

      {/* 3. Fleet Benchmarking */}
      <TurbineBenchmark
        currentTurbine={turbine}
        farmWindows={farmWindows}
        currentRecord={currentRecord}
      />
    </div>
  );
}
