"use client";

import React from "react";
import { useStream } from "../context/StreamContext";
import { Sidebar } from "../components/Sidebar";
import { Header } from "../components/Header";
import { OverviewView } from "../components/OverviewView";
import { TurbineDetailView } from "../components/TurbineDetailView";
import { BaselineView } from "../components/BaselineView";

export default function DashboardPage() {
  const { activeView } = useStream();

  return (
    <div className="flex min-h-screen bg-[#070a10]">
      {/* Global Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header />

        <main className="flex-1 overflow-y-auto">
          {activeView === "overview" && <OverviewView />}
          {activeView === "turbine" && <TurbineDetailView />}
          {activeView === "baseline" && <BaselineView />}
        </main>
      </div>
    </div>
  );
}
