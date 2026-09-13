"use client";

import React, { useState } from "react";
import { TurbineInfo, Subsystem } from "../lib/types";
import { RotateCw, AlertCircle } from "lucide-react";

interface TurbineVectorVisualProps {
  turbine: TurbineInfo;
}

export function TurbineVectorVisual({ turbine }: TurbineVectorVisualProps) {
  const [selectedSubsystem, setSelectedSubsystem] = useState<Subsystem>(
    turbine.faultSubsystem || "main_bearing"
  );
  const [isRotating, setIsRotating] = useState<boolean>(true);

  const isMainBearingFault = turbine.faultSubsystem === "main_bearing";
  const isPitchFault = turbine.faultSubsystem === "pitch_system";
  const isGeneratorFault = turbine.faultSubsystem === "generator";

  return (
    <div className="minimal-card p-6 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-bold text-white tracking-tight">
            Drive-Train Architecture
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Component health and subsystem mechanical inspection
          </p>
        </div>

        <button
          onClick={() => setIsRotating(!isRotating)}
          className="px-3 py-1 rounded-full text-xs font-medium bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 border border-white/[0.06] flex items-center gap-1.5 transition-all"
        >
          <RotateCw className={`w-3 h-3 ${isRotating ? "animate-spin" : ""}`} />
          <span>{isRotating ? "Rotor Spin On" : "Rotor Paused"}</span>
        </button>
      </div>

      {/* Clean Subsystem Pill Buttons */}
      <div className="flex items-center gap-1.5 mb-4 overflow-x-auto pb-1 text-xs">
        {[
          { id: "main_bearing" as Subsystem, label: "Main Bearing", fault: isMainBearingFault },
          { id: "gearbox" as Subsystem, label: "Gearbox", fault: false },
          { id: "generator" as Subsystem, label: "Generator", fault: isGeneratorFault },
          { id: "pitch_system" as Subsystem, label: "Pitch Actuator", fault: isPitchFault },
          { id: "rotor" as Subsystem, label: "Rotor Hub", fault: false },
        ].map((sub) => {
          const isCurrent = selectedSubsystem === sub.id;
          return (
            <button
              key={sub.id}
              onClick={() => setSelectedSubsystem(sub.id)}
              className={`px-3 py-1.5 rounded-full whitespace-nowrap transition-all font-medium text-xs flex items-center gap-1.5 ${
                sub.fault
                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                  : isCurrent
                  ? "bg-blue-600 text-white shadow-xs"
                  : "bg-white/[0.04] text-slate-400 hover:text-white border border-transparent"
              }`}
            >
              {sub.fault && <span className="w-1.5 h-1.5 rounded-full bg-rose-400 animate-ping" />}
              <span>{sub.label}</span>
            </button>
          );
        })}
      </div>

      {/* SVG Minimal Line-Art Vector */}
      <div className="relative w-full h-[260px] bg-[#10131c] rounded-2xl border border-white/[0.04] flex items-center justify-center overflow-hidden">
        <svg
          viewBox="0 0 680 320"
          className="w-full h-full p-4 select-none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Tower */}
          <path
            d="M 334 320 L 340 210 L 360 210 L 366 320 Z"
            fill="#181d28"
            stroke="#2d3748"
            strokeWidth="1.5"
          />

          {/* Nacelle Shell */}
          <path
            d="M 170 145 
               C 170 115, 230 100, 350 100 
               L 520 100 
               C 555 100, 565 120, 565 145 
               L 565 190 
               C 565 205, 540 205, 380 205 
               L 185 205 
               C 170 205, 170 170, 170 145 Z"
            fill="#151922"
            stroke="#2d3748"
            strokeWidth="1.5"
          />

          {/* Rotor Hub */}
          <path
            d="M 170 118 C 130 122, 95 145, 95 155 C 95 165, 130 188, 170 192 Z"
            fill={selectedSubsystem === "rotor" ? "#1e293b" : "#1a202c"}
            stroke="#3b485d"
            strokeWidth="1.5"
          />

          {/* Rotating Blades */}
          <g className={isRotating ? "animate-spin-slow origin-[95px_155px]" : ""}>
            <path d="M 95 155 L 40 40 L 52 40 Z" fill="#3b485d" opacity="0.6" />
            <path d="M 95 155 L 40 270 L 52 270 Z" fill="#3b485d" opacity="0.6" />
            <path d="M 95 155 L 10 150 L 10 160 Z" fill="#3b485d" opacity="0.6" />
          </g>

          {/* Low Speed Shaft */}
          <rect x="170" y="147" width="120" height="16" fill="#2d3748" />

          {/* MAIN BEARING (Highlighted if fault) */}
          <g
            className="cursor-pointer"
            onClick={() => setSelectedSubsystem("main_bearing")}
          >
            <rect
              x="195"
              y="132"
              width="45"
              height="46"
              rx="6"
              fill={isMainBearingFault ? "rgba(239, 68, 68, 0.2)" : "#1e293b"}
              stroke={isMainBearingFault ? "#ef4444" : "#4a5568"}
              strokeWidth={isMainBearingFault ? "2" : "1.5"}
            />
            <circle cx="217" cy="144" r="4" fill={isMainBearingFault ? "#ef4444" : "#a0aec0"} />
            <circle cx="217" cy="166" r="4" fill={isMainBearingFault ? "#ef4444" : "#a0aec0"} />
          </g>

          {/* GEARBOX */}
          <g
            className="cursor-pointer"
            onClick={() => setSelectedSubsystem("gearbox")}
          >
            <rect
              x="280"
              y="126"
              width="85"
              height="58"
              rx="8"
              fill="#1e293b"
              stroke="#4a5568"
              strokeWidth="1.5"
            />
            <circle cx="310" cy="155" r="16" fill="none" stroke="#4a5568" strokeWidth="1.5" strokeDasharray="4 2" />
            <circle cx="345" cy="155" r="10" fill="none" stroke="#4a5568" strokeWidth="1.5" strokeDasharray="3 2" />
          </g>

          {/* High Speed Shaft */}
          <rect x="365" y="152" width="35" height="6" fill="#4a5568" />

          {/* GENERATOR */}
          <g
            className="cursor-pointer"
            onClick={() => setSelectedSubsystem("generator")}
          >
            <rect
              x="400"
              y="126"
              width="100"
              height="58"
              rx="8"
              fill={isGeneratorFault ? "rgba(245, 158, 11, 0.2)" : "#1e293b"}
              stroke={isGeneratorFault ? "#f59e0b" : "#4a5568"}
              strokeWidth={isGeneratorFault ? "2" : "1.5"}
            />
            <line x1="425" y1="135" x2="425" y2="175" stroke={isGeneratorFault ? "#f59e0b" : "#4a5568"} strokeWidth="2.5" />
            <line x1="450" y1="135" x2="450" y2="175" stroke={isGeneratorFault ? "#f59e0b" : "#4a5568"} strokeWidth="2.5" />
            <line x1="475" y1="135" x2="475" y2="175" stroke={isGeneratorFault ? "#f59e0b" : "#4a5568"} strokeWidth="2.5" />
          </g>

          {/* Minimal Floating Alert Pill on Main Bearing */}
          {isMainBearingFault && (
            <g>
              <rect x="180" y="82" width="160" height="28" rx="14" fill="#2d1217" stroke="#ef4444" strokeWidth="1" />
              <text x="195" y="100" fill="#fca5a5" fontSize="11" fontFamily="sans-serif" fontWeight="600">
                Model class: {turbine.activeFault?.replaceAll("_", " ")}
              </text>
            </g>
          )}

          {/* Subsystem labels */}
          <text x="120" y="240" fill="#718096" fontSize="10" fontFamily="sans-serif">
            Rotor Hub
          </text>
          <text x="190" y="240" fill={isMainBearingFault ? "#ef4444" : "#718096"} fontSize="10" fontFamily="sans-serif" fontWeight={isMainBearingFault ? "bold" : "normal"}>
            Main Bearing
          </text>
          <text x="300" y="240" fill="#718096" fontSize="10" fontFamily="sans-serif">
            Gearbox
          </text>
          <text x="425" y="240" fill={isGeneratorFault ? "#f59e0b" : "#718096"} fontSize="10" fontFamily="sans-serif">
            Generator
          </text>
        </svg>

        {/* Selected pill tag */}
        <div className="absolute bottom-3 left-4 text-xs text-slate-400">
          Selected: <strong className="text-white capitalize">{selectedSubsystem.replace("_", " ")}</strong>
        </div>
      </div>
    </div>
  );
}
