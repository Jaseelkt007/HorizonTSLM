"use client";

import React, { createContext, useContext, useState } from "react";
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
  navigateToTurbine: (turbineId: string) => void;
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

  const setTimeframe = (tf: Timeframe) => {
    setTimeframeState(tf);
    // Keep the dashboard cards and chart on the same selected-farm snapshot.
    setFleetKPIs(getFleetKPIsForTimeframe(tf, selectedPlant));
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

  const selectedTurbine =
    turbines.find((t) => t.id === selectedTurbineId) || turbines[0];

  const navigateToTurbine = (turbineId: string) => {
    setSelectedTurbineId(turbineId);
    setActiveView("turbine");
  };

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
        navigateToTurbine,
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
