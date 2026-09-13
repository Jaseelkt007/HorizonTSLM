"use client";

import React from "react";
import { FleetPowerGraph } from "./FleetPowerGraph";
import { OverviewKPICards } from "./OverviewKPICards";
import { FleetStatusDonut } from "./FleetStatusDonut";
import { FarmMap } from "./FarmMap";
import { AlarmTicker } from "./AlarmTicker";

export function OverviewView() {
  return (
    <div className="space-y-6 p-8 max-w-[1500px] mx-auto">
      {/* Top Section: Left = Main Generation Profile, Right = KPI Stack */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8">
          <FleetPowerGraph />
        </div>
        <div className="lg:col-span-4">
          <OverviewKPICards />
        </div>
      </div>

      {/* Middle Section: Spatial Turbine Map + Fleet Health Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-7">
          <FarmMap />
        </div>
        <div className="lg:col-span-5">
          <FleetStatusDonut />
        </div>
      </div>

      {/* Bottom Section: Fleet Alarm Event Stream */}
      <div>
        <AlarmTicker />
      </div>
    </div>
  );
}
