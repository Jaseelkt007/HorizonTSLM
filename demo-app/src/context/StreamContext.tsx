"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import {
  ActiveView,
  Timeframe,
  TurbineInfo,
  FleetKPIs,
  AlarmEvent,
} from "../lib/types";
import {
  INITIAL_TURBINES,
  INITIAL_FLEET_KPIS,
  INITIAL_ALARMS,
  PLANTS,
  getFleetKPIsForTimeframe,
  getFarmTurbines,
  getFarmFleetKPIs,
  getFarmAlarms,
} from "../lib/mock-data";

interface StreamContextType {
  activeView: ActiveView;
  setActiveView: (view: ActiveView) => void;
  selectedPlant: string;
  setSelectedPlant: (plantId: string) => void;
  selectedTurbineId: string;
  setSelectedTurbineId: (id: string) => void;
  timeframe: Timeframe;
  setTimeframe: (tf: Timeframe) => void;
  turbines: TurbineInfo[];
  selectedTurbine: TurbineInfo;
  fleetKPIs: FleetKPIs;
  alarms: AlarmEvent[];
  isStreaming: boolean;
  toggleStreaming: () => void;
  streamSpeed: number;
  setStreamSpeed: (speed: number) => void;
  tickOffset: number;
  derateTurbine: (turbineId: string, percentage: number) => void;
  acknowledgeAlarm: (alarmId: string) => void;
  navigateToTurbine: (turbineId: string) => void;
  actionToast: string | null;
  clearActionToast: () => void;
}

const StreamContext = createContext<StreamContextType | undefined>(undefined);

export function StreamProvider({ children }: { children: React.ReactNode }) {
  const [activeView, setActiveView] = useState<ActiveView>("overview");
  const [selectedPlant, setSelectedPlantState] = useState<string>("kelmarsh");
  const [selectedTurbineId, setSelectedTurbineId] = useState<string>("T-01");
  const [timeframe, setTimeframeState] = useState<Timeframe>("24h");
  const [turbines, setTurbines] = useState<TurbineInfo[]>(INITIAL_TURBINES);
  const [fleetKPIs, setFleetKPIs] = useState<FleetKPIs>(INITIAL_FLEET_KPIS);
  const [alarms, setAlarms] = useState<AlarmEvent[]>(INITIAL_ALARMS);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [streamSpeed, setStreamSpeed] = useState<number>(1);
  const [tickOffset, setTickOffset] = useState<number>(0);
  const [actionToast, setActionToast] = useState<string | null>(null);

  const setTimeframe = (tf: Timeframe) => {
    setTimeframeState(tf);
    setFleetKPIs(getFleetKPIsForTimeframe(tf));
  };

  const setSelectedPlant = (plantId: string) => {
    setSelectedPlantState(plantId);
    const farmTurbs = getFarmTurbines(plantId);
    setTurbines(farmTurbs);
    setFleetKPIs(getFarmFleetKPIs(plantId, timeframe));
    setAlarms(getFarmAlarms(plantId));
    if (!farmTurbs.some((t) => t.id === selectedTurbineId)) {
      setSelectedTurbineId(farmTurbs[0]?.id || "T-01");
    }
  };

  // Optional live oscillation ticker when user explicitly enables live stream
  useEffect(() => {
    if (!isStreaming) return;

    const intervalMs = Math.max(1000, 2400 / streamSpeed);
    const interval = setInterval(() => {
      setTickOffset((prev) => (prev + 1) % 1000);

      // Subtle real-time wobble
      setTurbines((prev) =>
        prev.map((turb) => {
          const jitter = (Math.random() - 0.49) * 2;
          return {
            ...turb,
            activePower: Math.round(Math.max(0, Math.min(turb.ratedPower, turb.activePower + jitter))),
          };
        })
      );
    }, intervalMs);

    return () => clearInterval(interval);
  }, [isStreaming, streamSpeed]);

  const selectedTurbine =
    turbines.find((t) => t.id === selectedTurbineId) || turbines[0];

  const toggleStreaming = () => setIsStreaming((prev) => !prev);

  const navigateToTurbine = (turbineId: string) => {
    setSelectedTurbineId(turbineId);
    setActiveView("turbine");
  };

  const derateTurbine = (turbineId: string, percentage: number) => {
    setTurbines((prev) =>
      prev.map((t) => {
        if (t.id === turbineId) {
          const newPower = Math.round(t.ratedPower * (percentage / 100));
          return {
            ...t,
            activePower: newPower,
            status: "warning",
            actionRecommendation: `Operator derate applied: machine clamped to ${percentage}% rated output. Borescope inspection ticket #SCADA-9482 dispatched.`,
            diagnosticSummary: `${t.diagnosticSummary} [DERATE APPLIED: ${percentage}%]`,
          };
        }
        return t;
      })
    );
    setActionToast(`Successfully derated ${turbineId} to ${percentage}% rated capacity (1,230 kW). Inspection ticket #SCADA-9482 dispatched.`);
    setTimeout(() => {
      setActionToast(null);
    }, 6000);
  };

  const acknowledgeAlarm = (alarmId: string) => {
    setAlarms((prev) =>
      prev.map((a) => (a.id === alarmId ? { ...a, active: false } : a))
    );
    setActionToast(`Alarm ${alarmId} acknowledged by operator.`);
    setTimeout(() => {
      setActionToast(null);
    }, 4000);
  };

  const clearActionToast = () => setActionToast(null);

  return (
    <StreamContext.Provider
      value={{
        activeView,
        setActiveView,
        selectedPlant,
        setSelectedPlant,
        selectedTurbineId,
        setSelectedTurbineId,
        timeframe,
        setTimeframe,
        turbines,
        selectedTurbine,
        fleetKPIs,
        alarms,
        isStreaming,
        toggleStreaming,
        streamSpeed,
        setStreamSpeed,
        tickOffset,
        derateTurbine,
        acknowledgeAlarm,
        navigateToTurbine,
        actionToast,
        clearActionToast,
      }}
    >
      {children}
    </StreamContext.Provider>
  );
}

export function useStream() {
  const context = useContext(StreamContext);
  if (!context) {
    throw new Error("useStream must be used within a StreamProvider");
  }
  return context;
}
